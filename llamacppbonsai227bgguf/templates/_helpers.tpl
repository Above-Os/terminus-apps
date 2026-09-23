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
{{- /* llamacppbonsai227bgguf.presetArgs: resolve the shared-pool preset for an
       install whose stored ENGINE_ARGS matches a previous default preset.
       Both the engine container and llm-init must call this: llm-init's value
       becomes the model card, and Router derives admission width from that
       card. Match complete old presets rather than individual flags,
       which would also catch a hand-tuned -np 12. Keep $preset byte-identical
       to ENGINE_ARGS.default in OlaresManifest.yaml.
       Migrate only the exact previous default; preserve custom arguments.
       Usage: {{ include "llamacppbonsai227bgguf.presetArgs" ($oe.ENGINE_ARGS | default "") }} */ -}}
{{- define "llamacppbonsai227bgguf.presetArgs" -}}
{{- $args := trim (. | default "") -}}
{{- $preset := "-c 98304 -ngl all -fa on --jinja -np 1 --kv-unified -ctk q8_0 -ctv q8_0 -b 512 -ub 128" -}}
{{- if or (eq $args "") (eq $args "-c 32768 -ngl all -fa on --jinja -np 2 --kv-unified") -}}
{{- $preset -}}
{{- else -}}
{{- $args -}}
{{- end -}}
{{- end -}}
{{- /* llamacppbonsai227bgguf.engineArgs: pass ENGINE_ARGS through unchanged.
       Usage: {{ include "llamacppbonsai227bgguf.engineArgs" (dict "Args" $engineArgs) }} */ -}}
{{- define "llamacppbonsai227bgguf.engineArgs" -}}
{{- $in := . -}}
{{- trim ($in.Args | default "") -}}
{{- end -}}
