{{- define "surya2ocr.gpuMiB" -}}
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

{{- define "surya2ocr.llmInitTag" -}}v1.7.21{{- end -}}
{{- define "surya2ocr.ocrAdapterImage" -}}docker.io/beclab/ocr-adapter:v0.0.10{{- end -}}
{{- /* Olares accelerator mode selected at install time. */ -}}
{{- define "surya2ocr.gpuType" -}}
{{- $gpuObj := .Values.GPU | default dict -}}
{{- $gpuType := .Values.gpu | default "" -}}
{{- if not $gpuType -}}
{{- $gpuType = $gpuObj.Type | default "nvidia" -}}
{{- end -}}
{{- $gpuType -}}
{{- end -}}
{{- /* Select CUDA for NVIDIA/GB10, ROCm for AMD dGPU, and SYCL for Intel dGPU. */ -}}
{{- define "surya2ocr.llamacppImage" -}}
{{- $gpuType := include "surya2ocr.gpuType" . -}}
{{- $images := .Values.engine.images | default dict -}}
{{- if eq $gpuType "amd-gpu" -}}
{{- $images.amdGpu | default "docker.io/beclab/ggml-org-llama.cpp:server-rocm-b10731" -}}
{{- else if eq $gpuType "intel-gpu" -}}
{{- $images.intelGpu | default "docker.io/beclab/ggml-org-llama.cpp:server-intel-b10752" -}}
{{- else if eq $gpuType "nvidia-gb10" -}}
{{- $images.nvidiaGb10 | default "docker.io/beclab/ggml-org-llama.cpp:server-cuda12-b10143" -}}
{{- else -}}
{{- $images.nvidia | default "docker.io/beclab/ggml-org-llama.cpp:server-cuda12-b10143" -}}
{{- end -}}
{{- end -}}

{{- /* Separate downloads ensure both the model and vision projector are cached. */ -}}
{{- define "surya2ocr.modelSource" -}}
hf://datalab-to/surya-ocr-2-gguf --include surya-2.gguf,hf://datalab-to/surya-ocr-2-gguf --include surya-2-mmproj.gguf
{{- end -}}

{{- define "surya2ocr.modelName" -}}surya2{{- end -}}

{{- define "surya2ocr.redisURL" -}}
{{- $r := .Values.redis | default dict -}}
{{- $host := $r.host | default "redis" -}}
{{- $port := $r.port | default "6379" -}}
{{- $pass := $r.password | default "" -}}
{{- if $pass -}}
redis://:{{ $pass }}@{{ $host }}:{{ $port }}/0
{{- else -}}
redis://{{ $host }}:{{ $port }}/0
{{- end -}}
{{- end -}}
