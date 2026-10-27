"""Exercise disposable Studio training runs using the container's test password."""

import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time
import uuid

import requests

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=('complete', 'cancel-prep', 'cancel-training'))
mode = parser.parse_args().mode
lock = open('/tmp/codex-unsloth-api.lock', 'w')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(0)
log = Path('/tmp/codex-unsloth-api-' + mode + '.jsonl')
session = requests.Session()
base = 'http://127.0.0.1:8000'
auth = session.post(base + '/api/auth/login', json={
    'username': 'unsloth', 'password': os.environ['UNSLOTH_STUDIO_PASSWORD']}, timeout=30)
auth.raise_for_status()
session.headers['Authorization'] = 'Bearer ' + auth.json()['access_token']


def record(event, value):
    entry = {'time': time.time(), 'event': event, 'value': value}
    with log.open('a') as f:
        f.write(json.dumps(entry) + '\n')


try:
    request = {
        'start_request_id': 'codex-007-' + mode + '-' + uuid.uuid4().hex[:12],
        'project_name': 'codex-runtime-' + mode,
        'model_name': 'Qwen/Qwen3.5-2B',
        'model_known_cached': True,
        'training_type': 'LoRA/QLoRA',
        'hf_dataset': 'mlabonne/FineTome-100k',
        'format_type': 'auto',
        'dataset_slice_start': 0, 'dataset_slice_end': 31,
        'max_steps': 2 if mode == 'complete' else 1000,
        'max_seq_length': 128, 'batch_size': 1,
        'gradient_accumulation_steps': 1, 'lora_r': 8, 'lora_alpha': 8,
        'load_in_4bit': True, 'save_steps': 100,
    }
    job_id = None
    # A completed run can still be exiting its GPU worker. A rejected request is
    # remembered by Studio, so each subsequent attempt needs a fresh request ID.
    for attempt in range(60):
        request['start_request_id'] = 'codex-007-' + mode + '-' + uuid.uuid4().hex[:12]
        response = session.post(base + '/api/train/start', json=request, timeout=180)
        record('start', {'code': response.status_code, 'body': response.json()})
        response.raise_for_status()
        result = response.json()
        if result.get('status') != 'error':
            job_id = result['job_id']
            break
        if result.get('error') == 'Training already active':
            time.sleep(3)
            continue
        raise RuntimeError(result)
    assert job_id, 'Previous training worker did not exit'
    previous = None
    cancelled = False
    active_seen = False
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        response = session.get(base + '/api/train/status', timeout=30)
        response.raise_for_status()
        status = response.json()
        assert status.get('job_id') == job_id, 'Another training run replaced the test'
        state = (status.get('phase'), status.get('message'), status.get('error'),
                 status.get('details', {}).get('step'))
        if state != previous:
            record('status', status)
            previous = state
        active = status.get('is_training_running', False)
        active_seen |= active
        job = status.get('job_id')
        should_cancel = (mode == 'cancel-prep' and active) or (
            mode == 'cancel-training' and status.get('details', {}).get('step', 0) >= 1)
        if should_cancel and not cancelled:
            cancelled = True
            result = session.post(base + '/api/train/stop', json={
                'save': False, 'expected_job_id': job}, timeout=30)
            record('cancel', {'code': result.status_code, 'body': result.json()})
            result.raise_for_status()
        if not active and active_seen:
            if status.get('error'):
                raise RuntimeError(status['error'])
            if mode == 'complete':
                assert status.get('details', {}).get('step', 0) >= 2, status
                output = status['details']['output_dir']
                assert Path(output).is_dir(), output
                adapters = list(Path(output).glob('adapter_model.*'))
                assert any(p.stat().st_size > 0 for p in adapters), output
                record('artifacts', {p.name: p.stat().st_size for p in adapters})
            else:
                assert cancelled, status
                for _ in range(3):
                    time.sleep(2)
                    fresh = session.get(base + '/api/train/status', timeout=30).json()
                    assert not fresh['is_training_running'], fresh
                record('stable_terminal', True)
            record('PASS', status)
            break
        time.sleep(2)
    else:
        raise TimeoutError('Training did not finish within 15 minutes')
except Exception as exc:
    record('FAIL', str(exc))
    # A failed test must not leave its own training job running.
    try:
        current = session.get(base + '/api/train/status', timeout=10).json()
        if job_id and current.get('job_id') == job_id and current.get('is_training_running'):
            session.post(base + '/api/train/stop', json={
                'save': False, 'expected_job_id': job_id}, timeout=30).raise_for_status()
    except Exception as cleanup_error:
        record('cleanup_error', str(cleanup_error))
    raise
