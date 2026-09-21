{{- /* llmbase.gpuMiB: normalize a GPU-memory quantity to a BARE MiB integer.
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

{{- /* Olares GPU mode at install: intel | intel-gpu. */ -}}
{{- define "llmbase.gpuType" -}}
{{- $gpuObj := .Values.GPU | default dict -}}
{{- $gpuType := .Values.gpu | default "" -}}
{{- if not $gpuType -}}
{{- $gpuType = $gpuObj.Type | default "intel" -}}
{{- end -}}
{{- $gpuType -}}
{{- end -}}

{{- /* vllmintelqwen359bv3.engineImage: Intel XPU vLLM image. */ -}}
{{- define "vllmintelqwen359bv3.engineImage" -}}
{{- $img := .Values.engine | default dict -}}
{{- $images := $img.images | default dict -}}
{{- $images.intel | default "docker.io/intel/vllm:0.21.0-ubuntu24.04-20260805" -}}
{{- end -}}

{{- /* Pass ENGINE_ARGS through unchanged. */ -}}
{{- define "vllmintelqwen359bv3.engineArgs" -}}
{{- trim (.Args | default "") -}}
{{- end -}}
