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
{{- /* llamacppqwen3627bggufv3.engineArgs: CPU mode auto-adds -ngl 0 unless user set -ngl.
       Usage: {{ include "llamacppqwen3627bggufv3.engineArgs" (dict "Args" $engineArgs "IsCpu" $isCpuMode) }} */ -}}
{{- define "llamacppqwen3627bggufv3.engineArgs" -}}
{{- $in := . -}}
{{- $args := trim ($in.Args | default "") -}}
{{- $isCpu := $in.IsCpu | default false -}}
{{- if and $isCpu (not (contains "-ngl" $args)) -}}
{{- if $args -}}
{{- $args = printf "%s -ngl 0" $args -}}
{{- else -}}
{{- $args = "-ngl 0" -}}
{{- end -}}
{{- end -}}
{{- $args -}}
{{- end -}}

{{- /* Resolve GPU type safely when the legacy GPU object is absent. */ -}}
{{- define "llamacppqwen3627bggufv3.gpuType" -}}
{{- $gpu := .Values.GPU | default dict -}}
{{- .Values.gpu | default $gpu.Type | default "nvidia" -}}
{{- end -}}
{{- /* Intel uses a single slot and batch/microbatch 2048 without MTP.
         Preserve complete user-supplied custom argument strings. */ -}}
{{- define "llamacppqwen3627bggufv3.platformArgs" -}}
{{- $args := trim (.Args | default "") -}}
{{- if and (or (eq .Gpu "intel") (eq .Gpu "intel-gpu")) (or (eq $args "") (eq $args "-c 131072 -ngl all -fa on -ctk q8_0 -ctv q8_0 --jinja -np 1")) -}}
-c 131072 -ngl all -fa on -ctk q8_0 -ctv q8_0 --jinja -np 1 -b 2048 -ub 2048
{{- else -}}
{{- $args -}}
{{- end -}}
{{- end -}}
