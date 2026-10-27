# Unsloth runtime verification

## System HF token retest, 2026-10-27

Retested the unchanged 0.0.8 package on the current device after the system HF
token was configured. Temporary alias: `unslothhftest`; NVIDIA GPU mode only.

- The runtime token matched the system token through a one-time HMAC comparison.
  The deployment references a Kubernetes Secret. No token or comparison digest
  was saved in the evidence.
- Hub and Studio inherited the token. Authenticated `whoami` succeeded through
  the configured system endpoint; an anonymous identity request returned 401.
- Forced configuration downloads for the public Qwen 0.5B repository and
  `google/gemma-3-270m-it` succeeded. The latter configuration also downloaded
  anonymously, so this does not verify gated-model authorization or full gated
  weight downloads. No license acceptance was performed.
- GPU chat returned 42 with all 25 layers offloaded; explicit unload returned
  GPU memory to 0 MiB. The authenticated Jupyter kernel reported CUDA available
  and the HF token configured.
- A two-step QLoRA training run completed and saved a 17,640,136-byte adapter.
  The later child-process observation found no remaining worker, so it supplies
  no additional evidence about the training worker's token environment.

Evidence is under `.tmp-unsloth-dist/token-retest/`, including `secret-check.json`,
`hf-auth-result.json`, `hf-identity-control.json`, `smoke-token.json`,
`jupyter-result.json`, and `training-complete.jsonl`.
The temporary app was uninstalled without deleting data and its Upload record
was deleted. The original `unsloth` app remained running.

## 0.0.8 upstream upgrade, 2026-10-27

Target: `docker.io/beclab/unsloth-unsloth:nightly-2026.10.26`.
Official source revision: `0ea04730dbcac3d5cea8440992c0454a0e0fb4ae`.
Runtime API version: `2026.10.9` (previous image: `2026.10.3`).
The amd64 mirror has the same configuration and all 44 layer digests as the
upstream image. Configuration digest:
`sha256:8a5bb44993cdc34c269fbdd0f52b8a8ce720e128adf1a4616504ccc10449424e`.

Environment: current `one` device, Olares 1.12.7, amd64, RTX 5090 Laptop GPU,
Time slicing. No profile switch was made. The original `unsloth` app was not
upgraded or removed. Test aliases were `unslothgpu`, `unslothu6`, `unslothu7`, and
an earlier `unslothfresh` download/initialization probe.

### Changes

- NVIDIA GPU installation only. The CPU accelerator entry is removed.
- Chat-model idle unload defaults to 300 seconds. `0` disables it, other enabled
  values must be at least 60. Saved Studio residency/auto-unload settings retain
  precedence. This does not unload training or other GPU workloads or return an
  Olares Memory slicing allocation to other apps.
- New `SYSTEM_HF_ENDPOINT` and `SYSTEM_HF_TOKEN` app references resolve
  `OLARES_SYSTEM_HUGGINGFACE_SERVICE` and `OLARES_SYSTEM_HUGGINGFACE_TOKEN`.
  The container receives the standard `HF_ENDPOINT` and `HF_TOKEN` names, with
  the token supplied by Secret. Separate app-reference names prevent preserved
  legacy app-level HF values from overriding system settings during upgrades.
- Runtime image and package-directory tags are pinned in the helpers so saved
  old image values cannot retain the older runtime or its compiled extensions.
- The compatibility preparer copies the newer native training cleanup unchanged.
  Its checked fallback remains available for the older source layout.

### Results

| Check | Result |
|:---|:---|
| Chart lint, GPU-only declaration, system-variable references | Passed |
| Render with system HF placeholders, conflicting legacy HF values, idle timeout 0, saved old image values | Passed chart lint and source assertions. No placeholder credential requests were made |
| Native descendant-cleanup regression using new source on Linux | Five checks passed |
| Real 0.0.6 and 0.0.7 baselines | Login, GPU chat, project/thread/message/file fixtures, three SQLite backups and integrity checks passed |
| Both baseline upgrades | Same app identity and storage retained. Original account login, record IDs, contents, timestamps, project/thread/message links, attachment metadata and file SHA256 matched. Subsequent project writes passed |
| New upstream runtime installation | Passed Studio login, Jupyter entrance, fully offloaded 25-layer Qwen2.5-0.5B GGUF chat, expected answer 42, explicit unload to 0 MiB |
| Final system HF mapping on all three running instances | Container, Studio, Hub library and Jupyter kernel endpoint digests matched the configured system value. Training-related child processes inherited the same digest |
| Jupyter | Password-authenticated API session, real kernel execution with CUDA True, and kernel cleanup passed on all three instances |
| Local-data training | Dataset uploaded through the official upload endpoint. QLoRA completed 2/2 steps on 32 synthetic chat rows and saved a 17,640,136-byte adapter |
| Cancellation during preparation | Stop accepted, stable stopped state confirmed |
| Cancellation after training started | Stop accepted after 17 steps, stable stopped state confirmed |
| 300-second chat idle unload on upgraded instance | No manual unload. First sampled 0 MiB at 316.75 seconds, loaded list empty by the final check at 331.83 seconds. Log confirmed unload after 300 seconds idle |
| 0 / 60 / 300 configuration | Separate processes using the installed native reader returned 0 / 60 / 300. Not a full restart test for each value |
| Stop and resume | Upgraded 0.0.7 baseline recreated its pod, retained the new image/API and original test data, and passed GPU chat/unload again |

Both old charts use `nightly-2026.10.10`. These are two real package baselines,
not two different upstream images. Test alias patch numbers were incremented
for immutable Upload records during registry routing and HF compatibility
iterations. The formal candidate is 0.0.8, one patch above remote 0.0.7.

### Limits and observations

- In the initial upgrade run, no system HF token was configured (see the later
  real-token retest above). Secret rendering was checked with a dummy
  value and absence was verified at runtime. Real authenticated gated-model
  access was not tested. No token values are in the evidence.
- Runtime checks used REST and Jupyter kernel WebSocket APIs. Browser GUI clicks,
  GGUF export, image/video/audio generation and scheduled tasks were not tested
  in this upgrade run.
- After a completed training run, new starts temporarily reported Training
  already active while the previous worker exited. The bounded retry then
  started a subsequent job without restarting the app.
- After cancelled training, one final snapshot showed no active training and
  285 MiB of GPU memory still attributed to the app. Its cause was not diagnosed.
  Chat-model idle unload is not a guarantee of zero VRAM after every workflow.
  The test app was then stopped/uninstalled during cleanup.
- The first training attempt used a workspace dataset path and was correctly
  rejected by dataset-root validation. The successful test uploaded the same
  synthetic rows through the supported dataset endpoint.
- Initial image pulls hit mirror HTTP 502, stalled range reads and Docker Hub
  TLS timeouts. The mirror later recovered, completed the pull and the above
  runtime checks passed. A failed pull's 100% log line was not counted as success.

Evidence and scripts: `.tmp-unsloth-dist/upgrade-20261026/` in the task workspace.
Migration database/file backups remain in each test app's retained application
workspace. All four task-created test apps were uninstalled and their Upload
records were deleted. Exact-name queries confirmed they were no longer visible.
Application-data deletion was not requested. The original app remains running
and its data is kept.
No public market publication or PR is implied by this test report.

## 0.0.7 runtime regression

Tested on 2026-10-20 with Olares 1.12.7, amd64, an NVIDIA RTX 5090 Laptop GPU
(24 GiB, TimeSlice), and `unsloth/unsloth:nightly-2026.10.10`. The application and
all dependency installation tests run as UID/GID 1000. The image is unchanged.

## Changes under test

- uv and pip caches use app-private node-local Cache storage.
- uv's `[pip].target` configuration and `PIP_TARGET` install dynamic packages into
  `Data/unsloth/studio/runtime-packages/<image-tag>`. Studio and its children load
  that directory through `PYTHONPATH`. A new image tag gets a separate directory
  for compiled Python/PyTorch/CUDA extensions.
- `HF_HUB_DISABLE_XET=1` is set before the backend and workers start.
- A small, checked backport terminates and reaps the training worker's descendants
  before finalizing forced cancellation. The existing job identity guard,
  cooperative stop/save and history finalization remain unchanged. Cancellation
  escalates after 15 seconds; process cleanup and finalization can add time.
- An init container prepares the patched module in an ephemeral volume. The main
  container mounts it read-only. Unexpected source layouts fail initialization.
  The Pod template includes the patch checksum so patch changes trigger rollout.

The backport is specific to the pinned Studio image. Review/remove it when an
upstream image includes equivalent descendant cleanup; do not carry it across an
image upgrade without running the regression tests.

## Results

| Check | Result |
| --- | --- |
| Olares chart lint, owner and non-owner render scenarios | Pass |
| Baseline 0.0.5 install, upgrade to candidate | Pass |
| UID 1000 offline uv and pip installations into the configured directory | Pass |
| Real `causal-conv1d` installation and fresh-process CUDA extension import | Pass |
| Dependency persistence and import after Pod recreation during upgrade | Pass |
| Fresh-cache HTTP download of an Xet-backed official Hub weight | Pass |
| Backport regression, including a real installer ignoring SIGTERM, baseline orphan reproduction, and superseded-worker guard | 5 passed |
| Upstream stop watchdog, terminal state, start idempotency, and shutdown/save tests | 112 passed |
| Browser: cancel during preparation, wait for stopped state, reload | Pass; configuration page restored without a stop dialog |
| Qwen3.5-2B two-step QLoRA through Studio API, adapter saved | Pass; step 2/2, final loss 1.302899 |
| Configured Hub mirror, fresh-cache HTTP weight download | Pass with a 60-second transfer timeout in the test process |
| Final candidate: cancel while preparing/importing, terminal stability | Pass; stopped about 24 seconds after cancel, no remaining training workers |
| Final candidate: cancel after a real optimizer step, terminal stability | Pass; stopped about 4 seconds after cancel, output directory cleared |

The HTTP test downloaded `hf-internal-testing/tiny-random-LlamaForCausalLM` /
`model.safetensors` into a new temporary cache. Xet metadata was present; the test
forbids calling `xet_get` and verifies `http_get` was called. The result was
4,131,280 bytes with SHA256
`49c20f32c6c597480fcaec5df2f86c645eabea765cbea1e67886dbae45e5c992`.
The device's configured Hub mirror does not return Xet metadata, so the
Xet-specific assertion was tested against `https://huggingface.co` in the test
process only.
The mirror initially hit the library's default transfer timeout. Retesting with
`HF_HUB_DOWNLOAD_TIMEOUT=60` in the test process succeeded with the same SHA256;
the application's configured Hub endpoint and timeout were not changed. The
download fixture is pinned to revision `9fb191250dd56d0ba7ec9785a025ed29c03d5998`.

The completed training saved a 21,851,336-byte `adapter_model.safetensors`.
The image logged torch.compile eager-fallback warnings during the first run;
training completed and the adapter was saved. The completed GPU worker used the
existing upstream post-completion retirement watchdog before a subsequent run
could start. The test harness waits for that exit; the chart changes the
cancel-without-save timeout, not the post-completion timeout.

The upstream tests need the actual training module preloaded because the
watchdog test's import stubs otherwise mask `utils.paths.storage_roots` during
collection. No upstream test files were changed. The final run produced 112
passes with existing dependency deprecation/syntax warnings.

## Reproduce

Run these scripts with the Studio virtual environment's Python inside the test
container. Copy the scripts to a temporary directory first; `tests/` and this
document are excluded from the installable chart by `.helmignore`.

```sh
PY=/opt/unsloth-studio/unsloth_studio/bin/python

# After Studio or its official install-kernels command installs causal-conv1d:
$PY verify_dependencies.py
$PY verify_http_download.py --endpoint https://huggingface.co --require-xet

# Use the original, unpatched module from the pinned image for this source test:
$PY verify_cancellation.py /tmp/original-training.py prepare-runtime.py -v

# Uses the container's install-time password without printing credentials.
# Creates disposable training runs and writes progress logs under /tmp.
$PY verify_training.py complete
$PY verify_training.py cancel-prep
$PY verify_training.py cancel-training
```

`verify_training.py` uses `Qwen/Qwen3.5-2B`, 32 rows from
`mlabonne/FineTome-100k`, QLoRA, sequence length 128, batch size 1, LoRA rank 8,
and two steps for the completion case. The cancellation cases use a longer run.
Verify the completion case produces a nonempty adapter, and verify terminal
state remains stable after cancellation and page reload.

For the upstream suite, preload `core.training.training` with the backend source
directory on `sys.path`, then run pytest on:

- `tests/test_training_stop_watchdog.py`
- `tests/test_training_status_terminal.py`
- `tests/test_training_start_idempotency.py`
- `tests/test_training_shutdown_stop.py`

Use a writable pytest cache such as `/tmp/unsloth-pytest-cache`.
