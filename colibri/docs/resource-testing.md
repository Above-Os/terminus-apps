# Resource configuration and test observations

This chart lets users choose system RAM and GPU-memory limits. The listing keeps the performance explanation short; this document records the settings and observations behind it.

## Configuration

- `MEMORY_LIMIT` is required at installation, has no default and remains editable. Enter whole `Mi` or `Gi` quantities, for example `32Gi` or `48Gi`. The chart accepts a minimum of `2Gi`; model requirements can be much higher. Changes restart the app and reload its saved model.
- The main container reserves a fixed `256Mi`. The engine RAM budget is calculated automatically as `floor(limit_bytes * 0.75 / 1_000_000_000)` decimal GB: `32Gi` becomes 25 GB and `48Gi` becomes 38 GB. Users no longer need `RAM_GB` or `MEMORY_REQUEST`. The remaining headroom is a starting policy, not a guarantee against running out of memory.
- `GPU_MEMORY_LIMIT` is required without a default. The chart has one NVIDIA installation entry. Enter a whole `Mi`/`Gi` quota of at least `4Gi`, or enter `0` to disable CUDA and run inference on the CPU. There is no separate CPU compute-mode option. The zero path requests no NVIDIA resource in the pod, while Olares still records an NVIDIA device binding and requires an NVIDIA-capable node.
- Olares receives the entire positive GPU quota. The engine placement budget subtracts a fixed `2Gi` for CUDA/runtime buffers. This placement budget is shared by weights and expert cache; the allocation is not necessarily occupied immediately.
- GPU allocation is installation-time only and is read-only afterward. To change it, uninstall **with data retained** and reinstall with the new quota; changing an engine environment variable alone does not reallocate the GPU.
- Both `standard` and `low-memory-moe` use these resource budgets. Standard enables CUDA chain execution; low-memory MoE uses staged execution. The former fixed low-memory RAM/GPU preset has been removed.
- Context defaults to 16,384 tokens; 32K, 64K and 128K remain selectable where the model/resources permit. Increasing the context limit does not establish that a maximum-length input will fit or respond quickly.

## Test conditions

- Olares One, Olares 1.12.7, RTX 5090 Laptop GPU; node RAM capacity 98,234,688 Ki (about 93.68 GiB).
- Existing `Qwen3.6-35B-A3B-UD-IQ4_XS.gguf`, 17,730,509,792 bytes; image `beclab/harveyff-colibri:2.1.0-0a5504a-cuda130-models5`.
- Standard mode, main-container CPU limit 8 cores, context limit 16,384, temperature 0 and thinking disabled.
- Each setting has two sequential streaming requests: 1,034 input tokens and 128 output tokens. A/B input markers differ. The input is repetitive synthetic text and the output is sequential counting.
- TTFT is elapsed time inside the app to the first non-empty text delta. Decode rate is estimated as `(completion_tokens - 1) / (last_text_time - first_text_time)`. External browser/proxy delay is excluded.
- First/second request values below are observations, not strict cold/warm classifications. Host file cache can survive between settings and containers.

## GPU quota comparison

Measured with chart 0.2.32, before the CPU-only option was added. RAM limit is fixed at `48Gi` (engine budget 38 decimal GB). The positive-GPU budget policy is retained in 0.2.34.

| GPU quota | Placement budget | TTFT, first / second (s) | Decode, first / second (token/s) |
|---|---|---:|---:|
| 4Gi | 2Gi | 13.90 / 5.89 | 24.87 / 30.57 |
| 8Gi | 6Gi | 1.27 / 1.87 | 37.33 / 39.81 |
| 12Gi | 10Gi | 0.75 / 0.98 | 39.01 / 46.71 |
| 16Gi | 14Gi | 1.32 / 0.73 | 67.35 / 68.80 |
| 20Gi | 18Gi | 0.62 / 0.25 | 168.83 / 171.13 |

At `20Gi`, the engine reported all 10,240 experts resident in VRAM. This explains the larger gain for this particular model; it is not a universal threshold for other models.

## CPU-only and RAM-limit comparison

Measured with chart 0.2.33. The CPU-only row has no GPU allocation. All other rows use an `8Gi` GPU quota (6 GiB placement budget).

| RAM limit | GPU quota | TTFT, first / second (s) | Decode, first / second (token/s) |
|---|---|---:|---:|
| 48Gi | 0Gi | 18.20 / 8.94 | 18.34 / 20.38 |
| 48Gi | 8Gi | 1.71 / 1.88 | 42.08 / 42.92 |
| 32Gi | 8Gi | 0.88 / 2.01 | 42.12 / 35.30 |
| 24Gi | 8Gi | 40.71 / 30.98 | 21.22 / 22.80 |
| 16Gi | 8Gi | 38.92 / 33.82 | 21.17 / 20.45 |
| 12Gi | 8Gi | 63.47 / 58.05 | 15.33 / 16.32 |
| 8Gi | 8Gi | 72.39 / 68.61 | 10.33 / 11.18 |

All 14 requests in this comparison completed, with no OOM kills or engine restarts. CPU-only execution was verified by actual resource requests, `COLI_CUDA=0` and the absence of NVIDIA devices.

With the GPU fixed at `8Gi`, both `32Gi` and `48Gi` RAM settings kept all experts resident in RAM and achieved approximately two-second second-request TTFT. `32Gi` was the smallest **tested** setting with this behavior; no settings between 24 and 32 GiB were tested. At lower RAM limits, requests still completed, but the input-processing delay grew substantially.

## Long-input observation

A separate 20Gi-GPU, 48Gi-RAM test of 14,786 input tokens and 128 output tokens completed in standard mode: TTFT 3.53 s and total time 4.34 s. The staged low-memory mode also completed at the same token lengths, but was observed still processing input without text at 250.097 s. Its exact final response time was not retained, so no precise completion latency is reported. Larger GPU budgets alone do not remove the staged mode's long-input delay.

## Limits of these measurements

- The machine and GPU are shared. Each setting has only two requests; these results are not a statistical or exclusive-GPU benchmark.
- A container cap of 8 or 12 GiB on a roughly 94 GiB host is **not** a test on a machine with only that much physical RAM. Shared page cache may remain on the host, and mapped pages need not be charged anew to each container.
- Container memory samples include charged file cache and are not process RSS or a measurement of total host memory needed. Sampling can miss short peaks.
- These short-input comparisons do not validate every model, a full 16K prompt, larger contexts or concurrent workloads. Real conversations can have different cache behavior.
- GPU-memory observations during testing came from the HAMi quota view, not an independent host physical-VRAM measurement.
- The 75% RAM policy was retained. Successful completion of these requests does not prove that it is optimal or safe for all workloads.

After testing, the app was restored to chart 0.2.33, standard mode, `48Gi` RAM, `20Gi` GPU and a 16K context limit; the saved model was healthy.

## Single installation entry (0.2.34)

The standalone CPU resource-mode declaration is removed. Users enter RAM and GPU-memory limits through the same NVIDIA installation entry. A GPU quota of `0` selects CPU inference at runtime. The GPU quota must be at least `4Gi` when positive.

The preceding 0.2.33 NVIDIA-mode/zero-quota installation completed two 1,034-input/128-output-token requests. TTFT was 17.30 / 8.70 s and decode was 18.03 / 20.14 token/s. CUDA was disabled, the pod requested no NVIDIA resource and exposed no NVIDIA devices. Olares nevertheless retained a NVIDIA binding. The updated package is also checked without explicitly supplying a compute mode, to verify the single-entry installation path.

This is a runtime CPU fallback on an NVIDIA installation, not an installation option for hosts without an NVIDIA device. Test installations are removed with data retained, restoring the initial uninstalled state and original model selection.
