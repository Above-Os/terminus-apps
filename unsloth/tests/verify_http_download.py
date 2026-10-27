import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

parser = argparse.ArgumentParser()
parser.add_argument('--endpoint')
parser.add_argument('--require-xet', action='store_true')
args = parser.parse_args()
if args.endpoint:
    os.environ['HF_ENDPOINT'] = args.endpoint

from huggingface_hub import constants, get_hf_file_metadata, hf_hub_download, hf_hub_url
from huggingface_hub import file_download

assert constants.HF_HUB_DISABLE_XET
repo = 'hf-internal-testing/tiny-random-LlamaForCausalLM'
filename = 'model.safetensors'
revision = '9fb191250dd56d0ba7ec9785a025ed29c03d5998'
metadata = get_hf_file_metadata(hf_hub_url(repo, filename, revision=revision), timeout=30)
if args.require_xet:
    assert metadata.xet_file_data is not None, 'Test must exercise an Xet-backed weight'
with tempfile.TemporaryDirectory(prefix='http-regression-', dir='/cache/python') as cache:
    with patch.object(file_download, 'xet_get', side_effect=AssertionError('Xet invoked')):
        with patch.object(file_download, 'http_get', wraps=file_download.http_get) as http:
            result = Path(hf_hub_download(repo, filename, revision=revision,
                                         cache_dir=cache, etag_timeout=30))
            assert http.call_count >= 1, 'No HTTP transfer occurred'
    digest = hashlib.sha256(result.read_bytes()).hexdigest()
    assert result.stat().st_size == metadata.size
    expected = '49c20f32c6c597480fcaec5df2f86c645eabea765cbea1e67886dbae45e5c992'
    assert digest == expected, f'Downloaded weight checksum mismatch: {digest}'
    print(json.dumps({'PASS': True, 'repo': repo, 'file': filename,
                      'bytes': metadata.size, 'sha256': digest,
                      'xet_backed': metadata.xet_file_data is not None,
                      'transport': 'HTTP'}), flush=True)
