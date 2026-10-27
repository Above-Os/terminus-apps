{{- /* llmbase.gpuMiB: normalize a GPU-memory quantity to a BARE MiB integer.
       Accepts 8Gi / 8G / 8192Mi / 8192M / 8192 and returns MiB.
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
{{- /* vllmintelqwen3827bmtpv3.engineArgs: pass ENGINE_ARGS through unchanged.
       Usage: {{ include "vllmintelqwen3827bmtpv3.engineArgs" (dict "Args" $engineArgs) }} */ -}}
{{- define "vllmintelqwen3827bmtpv3.engineArgs" -}}
{{- $in := . -}}
{{- trim ($in.Args | default "") -}}
{{- end -}}
{{- /* Olares GPU mode at install. This chart only offers intel-gpu. */ -}}
{{- define "llmbase.gpuType" -}}
{{- $gpuObj := .Values.GPU | default dict -}}
{{- $gpuType := .Values.gpu | default "" -}}
{{- if not $gpuType -}}
{{- $gpuType = $gpuObj.Type | default "intel-gpu" -}}
{{- end -}}
{{- $gpuType -}}
{{- end -}}
{{- define "vllmintelqwen3827bmtpv3.engineImage" -}}
{{- $img := .Values.engine.images | default dict -}}
{{- $img.intelGpu | default "docker.io/beclab/llm-scaler-vllm:0.26.0-b2-pp-mtp-263b3a7" -}}
{{- end -}}
