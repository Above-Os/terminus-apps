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
{{- /* sglangqwen359bbyaudiov3.engineArgs: CPU mode auto-adds --device cpu unless already set.
       Chat turns thinking off by default: Qwen3.5 otherwise reasons before every
       answer, which cost voice replies seconds and, under a 1024-token budget, the
       whole reply. Added here rather than to the ENGINE_ARGS default because an
       upgrade keeps an installation's saved ENGINE_ARGS. A request can still turn
       it on with chat_template_kwargs, and an operator who sets the flag keeps theirs.
       Usage: {{ include "sglangqwen359bbyaudiov3.engineArgs" (dict "Args" $engineArgs "IsCpu" $isCpuMode) }} */ -}}
{{- define "sglangqwen359bbyaudiov3.engineArgs" -}}
{{- $in := . -}}
{{- $args := trim ($in.Args | default "") -}}
{{- $isCpu := $in.IsCpu | default false -}}
{{- if and $isCpu (not (contains "--device" $args)) -}}
{{- if $args -}}
{{- $args = printf "%s --device cpu" $args -}}
{{- else -}}
{{- $args = "--device cpu" -}}
{{- end -}}
{{- end -}}
{{- if not (or (contains "--default-chat-template-kwargs" $args) (contains "--is-embedding" $args)) -}}
{{- $args = trim (printf "%s --default-chat-template-kwargs {\"enable_thinking\":false}" $args) -}}
{{- end -}}
{{- $args -}}
{{- end -}}
