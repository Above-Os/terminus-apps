{{- /* llmbase.gpuMiB: normalize a GPU-memory quantity to a BARE MiB integer for
       HAMi's nvidia.com/gpumem. Its base unit is MiB and the value MUST be a
       plain integer — a Mi/Gi suffix is misread by the scheduler (e.g. "6144Mi"
       -> 6442450944). Accepts 8Gi / 8G / 8192Mi / 8192M / 8192 and returns MiB.
       Usage: {{ include "llmbase.gpuMiB" ($oe.X_REQUIRED_GPU_MEMORY | default "4096") }} */ -}}
{{- define "llmbase.gpuMiB" -}}
{{- $g := trim . -}}
{{- if hasSuffix "Gi" $g -}}
{{- mul (int (trimSuffix "Gi" $g)) 1024 -}}
{{- else if hasSuffix "G" $g -}}
{{- mul (int (trimSuffix "G" $g)) 1024 -}}
{{- else if hasSuffix "Mi" $g -}}
{{- int (trimSuffix "Mi" $g) -}}
{{- else if hasSuffix "M" $g -}}
{{- int (trimSuffix "M" $g) -}}
{{- else -}}
{{- int $g -}}
{{- end -}}
{{- end -}}
{{- /* Olares accelerator mode as app-service selected it at install:
       cpu | intel | nvidia | nvidia-gb10 | intel-gpu | amd-gpu | ...
       Only `nvidia` and `cpu` are declared in spec.accelerator, so only those
       two can reach these templates. */ -}}
{{- define "llamacppbonsai227bgguf.gpuType" -}}
{{- $gpuObj := .Values.GPU | default dict -}}
{{- $gpuType := .Values.gpu | default "" -}}
{{- if not $gpuType -}}
{{- $gpuType = $gpuObj.Type | default "cpu" -}}
{{- end -}}
{{- $gpuType -}}
{{- end -}}
{{- /* Anything that is not a discrete NVIDIA card runs the CPU build: no
       accelerator device, no nvidia.com/gpumem, no gpu-inject. */ -}}
{{- define "llamacppbonsai227bgguf.isCpu" -}}
{{- ne (include "llamacppbonsai227bgguf.gpuType" .) "nvidia" -}}
{{- end -}}
{{- /* Engine image per mode. Same PrismML fork build (prism-b10709-9a9394a),
       different ggml backend: the CUDA 12.8 asset vs the plain ubuntu-x64 one,
       which carries the full set of libggml-cpu-*.so and picks the µarch
       variant (haswell / alderlake / icelake / zen4 / ...) at runtime.
       There is deliberately no Vulkan variant here: the model card lists the
       supported backends as CUDA, Metal and CPU, and the Vulkan build does not
       come up on the target hardware. */ -}}
{{- define "llamacppbonsai227bgguf.engineImage" -}}
{{- if eq (include "llamacppbonsai227bgguf.isCpu" .) "true" -}}
docker.io/leamon2code/prismml-llama.cpp:server-cpu-prism-b10709
{{- else -}}
docker.io/leamon2code/prismml-llama.cpp:server-cuda12.8-prism-b10709
{{- end -}}
{{- end -}}
{{- /* Both modes serve the same PQ2_0 file, so switching modes re-uses the
       shared appCommon/huggingface cache and downloads nothing. PQ2_0 is also
       the right pick for CPU: the CPU backend carries repack_pq2_0_to_pq2_0_4_bl
       plus ggml_gemm/gemv_pq2_0_4x8_q8_0, while PTQ1_0 has only
       ggml_vec_dot_ptq1_0_q8_0 — no repacked GEMM path, so prompt processing
       would fall off a cliff. */ -}}
{{- /* llamacppbonsai227bgguf.presetArgs: resolve the preset for the selected
       mode. Both the engine container and llm-init must call this: llm-init's
       value becomes the model card, and Router derives admission width from
       that card. Match complete presets rather than individual flags, which
       would also catch a hand-tuned -np 12 — anything outside $known is a user
       edit and passes through untouched. Every previous default stays in
       $known, so an upgrade and a reinstall into the other mode both land on
       the preset that fits the hardware.
       Keep $nvidiaPreset byte-identical to ENGINE_ARGS.default in
       OlaresManifest.yaml: a fresh install of either mode starts from it, and
       the CPU branch rewrites from there.
       The CPU preset drops -ngl (no device to offload to), keeps -fa on (the
       Hadamard activation transform depends on it), stays at f16 K/V, and
       pins -t to the container CPU limit — without it llama.cpp sizes its
       threadpool from what it can see of the host and the threads fight over
       the cgroup quota. Retune -t together with LLAMACPP_CPU_LIMIT. */ -}}
{{- define "llamacppbonsai227bgguf.presetArgs" -}}
{{- $root := .Root -}}
{{- $args := trim (.Args | default "") -}}
{{- $nvidiaPreset := "-c 131072 -ngl all -fa on --jinja -np 1 --kv-unified -ctk q8_0 -ctv q8_0 -b 512 -ub 128" -}}
{{- $cpuPreset := "-c 131072 -fa on --jinja -np 1 --kv-unified -b 512 -ub 128 -t 8" -}}
{{- $known := list "" "-c 32768 -ngl all -fa on --jinja -np 2 --kv-unified" "-c 98304 -ngl all -fa on --jinja -np 1 --kv-unified -ctk q8_0 -ctv q8_0 -b 512 -ub 128" "-c 32768 -ngl all -fa on --jinja -np 1 --kv-unified -b 512 -ub 128" "-c 32768 -fa on --jinja -np 1 --kv-unified -b 512 -ub 128 -t 8" $nvidiaPreset $cpuPreset -}}
{{- $preset := $nvidiaPreset -}}
{{- if eq (include "llamacppbonsai227bgguf.isCpu" $root) "true" -}}
{{- $preset = $cpuPreset -}}
{{- end -}}
{{- if has $args $known -}}
{{- $preset -}}
{{- else -}}
{{- $args -}}
{{- end -}}
{{- end -}}
{{- /* Resolve arguments once for both the engine and the model-card handoff.
       Match --embedding as a complete flag, not part of another argument. */ -}}
{{- define "llamacppbonsai227bgguf.engineArgs" -}}
{{- $oe := .Values.olaresEnv | default dict -}}
{{- $args := include "llamacppbonsai227bgguf.presetArgs" (dict "Root" . "Args" ($oe.ENGINE_ARGS | default "")) -}}
{{- if and (eq ($oe.MODEL_MODE | default "") "embedding") (not (regexMatch `(^|\s)--embedding(\s|$)` $args)) -}}
{{- $args = trim (printf "%s --embedding" $args) -}}
{{- end -}}
{{- $args -}}
{{- end -}}
