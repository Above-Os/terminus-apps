# Preview validation

Tested on Olares 1.12.7, amd64, an NVIDIA RTX 5090 Laptop GPU (24 GiB class), with upstream commit 0a5504a1dc64f86fcd0fe7db298b0448c730e7e6.

## Completed runtime checks

- Current CUDA image: authenticated browser chat, multi-turn context, SSE, tool calls, OpenAI Completions, Anthropic Messages, cancellation/recovery, queued concurrent requests, host guard and internal-key isolation. 19 of 20 checks passed; forced JSON output returns the engine's unsupported-feature 400.
- Qwen3.8-27B UD-Q4_K_XL: approximately 8.1-9.0 tokens/s in short engine-wall-time measurements. A prior CPU image baseline was approximately 3.0 tokens/s. These measurements include prompt work and are not a decode-only benchmark against llama.cpp.
- 600.53-second soak: 76 short requests passed; one additional 512-token response completed in 66.65 seconds. Sampled engine RSS remained approximately 17.36 GB, with no engine or pod restarts.
- A 2,858-token prompt completed correctly in 140.86 seconds. An input of at least 4,805 tokens correctly failed the 4,096-token limit with compaction off, followed by successful generation. Automatic compaction entered summarization but exceeded a 300-second client limit: this check did not pass.
- Cached Qwen3.6-35B-A3B UD-IQ4_XS: three text generations passed with a 4 GB RAM budget and 2 GiB CUDA allowance. Engine RSS was approximately 3.3 GB, and recorded expert-file read time was 0.45-1.52 seconds per turn. This verifies the expert-file loading path, not physical SSD throughput or a minimum system RAM requirement.
- Restart and chart-only 0.2.2 -> 0.2.3 upgrade retained generated authentication, model metadata, GPU mode, Router config, model ID and an application-data marker. Both generated expected confirmation replies. No upstream engine version migration was tested.
- Stopping Colibri released GPU memory to approximately 60 MiB for the whole card. The pre-existing Qwen service was restored and Router default-chat returned a confirmation response.
- Browser local/Router switching and generation worked with an explicit Router URL. Theme and language survive reload; chat history and generation parameters do not. Shared weights were mounted read-only; test-only model metadata was cleaned up.

## Static validation for 0.2.6

- CPU/NVIDIA chart render checks, root/English copy parity, English/Chinese locale structure, required model input, public asset dimensions/availability, generated-secret references and absence of personal install URLs.
- The portable default uses https://router.<installing-user-zone>/v1, matching the existing Router entrance naming pattern. Explicit overrides remain supported. This new default was rendered but has not yet had a cross-account live install test.
- The prior CUDA image booted in CPU mode during upgrade, but the soak and broad functional suite above ran in NVIDIA mode. Fresh CPU-fallback functional testing with this image remains a preview check.

## Remaining scope

This stays draft for preview testing. GPU code targets sm_120, not older NVIDIA devices; ARM64 is not built or advertised. Long-context performance, automatic compaction completion, multi-hour endurance, other models and fresh installs on other accounts remain limited or unverified. Refresh persistence is an upstream UI limitation. Model weights are not downloaded automatically.
