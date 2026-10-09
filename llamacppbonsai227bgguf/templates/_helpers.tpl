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
{{- /* Olares selects cpu, nvidia or intel-gpu from spec.accelerator. */ -}}
{{- define "llamacppbonsai227bgguf.gpuType" -}}
{{- $gpuObj := .Values.GPU | default dict -}}
{{- .Values.gpu | default $gpuObj.Type | default "cpu" -}}
{{- end -}}
{{- define "llamacppbonsai227bgguf.isIntelGpu" -}}
{{- eq (include "llamacppbonsai227bgguf.gpuType" .) "intel-gpu" -}}
{{- end -}}
{{- define "llamacppbonsai227bgguf.isCpu" -}}
{{- eq (include "llamacppbonsai227bgguf.gpuType" .) "cpu" -}}
{{- end -}}
{{- /* All three backends use the PrismML fork and the same cached PQ2_0 model. */ -}}
{{- define "llamacppbonsai227bgguf.engineImage" -}}
{{- if eq (include "llamacppbonsai227bgguf.isCpu" .) "true" -}}
docker.io/beclab/leamon2code-prismml-llama.cpp:server-cpu-prism-b10709
{{- else if eq (include "llamacppbonsai227bgguf.isIntelGpu" .) "true" -}}
docker.io/beclab/leamon2code-prismml-llama.cpp:server-vulkan-prism-b10754
{{- else -}}
docker.io/beclab/leamon2code-prismml-llama.cpp:server-cuda12.8-prism-b10709
{{- end -}}
{{- end -}}
{{- /* Resolve the same preset for the engine and llm-init model card.
       Migrate known previous defaults across modes;
       preserve custom arguments. Intel discrete GPU offloads all layers with f16 K/V and
       one slot; CPU uses one slot without offloading. NVIDIA retains q8_0 K/V and two slots. */ -}}
{{- define "llamacppbonsai227bgguf.presetArgs" -}}
{{- $root := .Root -}}
{{- $args := trim (.Args | default "") -}}
{{- $nvidiaPreset := "-c 131072 -ngl all -fa on --jinja -np 2 -ctk q8_0 -ctv q8_0 -b 512 -ub 128" -}}
{{- $cpuPreset := "-c 131072 -fa on --jinja -np 1 --kv-unified -b 512 -ub 128 -t 8" -}}
{{- $intelGpuPreset := "-c 131072 -ngl all -fa on --jinja -np 1 --kv-unified -b 512 -ub 128 -t 8" -}}
{{- $known := list "" "-c 32768 -ngl all -fa on --jinja -np 2 --kv-unified" "-c 98304 -ngl all -fa on --jinja -np 1 --kv-unified -ctk q8_0 -ctv q8_0 -b 512 -ub 128" "-c 32768 -ngl all -fa on --jinja -np 1 --kv-unified -b 512 -ub 128" "-c 32768 -fa on --jinja -np 1 --kv-unified -b 512 -ub 128 -t 8" "-c 131072 -ngl all -fa on --jinja -np 1 --kv-unified -ctk q8_0 -ctv q8_0 -b 512 -ub 128" "-c 131072 -ngl all -fa on --jinja -np 1 -ctk q8_0 -ctv q8_0 -b 512 -ub 128" $nvidiaPreset $cpuPreset $intelGpuPreset -}}
{{- $preset := $nvidiaPreset -}}
{{- if eq (include "llamacppbonsai227bgguf.isCpu" $root) "true" -}}
{{- $preset = $cpuPreset -}}
{{- else if eq (include "llamacppbonsai227bgguf.isIntelGpu" $root) "true" -}}
{{- $preset = $intelGpuPreset -}}
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
