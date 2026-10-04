{{- /* paddleocrhybrid.gpuMiB: normalize GPU memory to bare MiB int for nvidia.com/gpumem. */ -}}
{{- define "paddleocrhybrid.gpuMiB" -}}
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

{{- /* Needs llm-init with ROLE=extra → extra_model_path (L6+). */ -}}
{{- define "paddleocrhybrid.llmInitTag" -}}v1.7.21{{- end -}}
{{- /* Needs OCRAdapter with paddle-hybrid pipeline (S11+). */ -}}
{{- define "paddleocrhybrid.ocrAdapterImage" -}}docker.io/beclab/ocr-adapter:v0.0.9{{- end -}}
{{- /* Olares accelerator mode selected at install time. */ -}}
{{- define "paddleocrhybrid.gpuType" -}}
{{- $gpuObj := .Values.GPU | default dict -}}
{{- $gpuType := .Values.gpu | default "" -}}
{{- if not $gpuType -}}
{{- $gpuType = $gpuObj.Type | default "nvidia" -}}
{{- end -}}
{{- $gpuType -}}
{{- end -}}
{{- /* Select a CUDA image for NVIDIA/GB10 and a SYCL image for Intel dGPU. */ -}}
{{- define "paddleocrhybrid.llamacppImage" -}}
{{- $gpuType := include "paddleocrhybrid.gpuType" . -}}
{{- $images := .Values.engine.images | default dict -}}
{{- if eq $gpuType "intel-gpu" -}}
{{- $images.intelGpu | default "docker.io/beclab/ggml-org-llama.cpp:server-intel-b10752" -}}
{{- else if eq $gpuType "nvidia-gb10" -}}
{{- $images.nvidiaGb10 | default "docker.io/beclab/ggml-org-llama.cpp:server-cuda12-b10143" -}}
{{- else -}}
{{- $images.nvidia | default "docker.io/beclab/ggml-org-llama.cpp:server-cuda12-b10143" -}}
{{- end -}}
{{- end -}}
{{- define "paddleocrhybrid.layoutImage" -}}docker.io/beclab/ocr-layout:v0.0.1-onnx-cpu{{- end -}}

{{- /* Whole-repo dual-source (no --include):
       1) VLM GGUF repo → ROLE=main (snapshot dir; wrapper picks .gguf + mmproj)
       2) layout ONNX repo → ROLE=extra → extra_model_path for ocrlayout.sh */ -}}
{{- define "paddleocrhybrid.modelSource" -}}
hf://PaddlePaddle/PaddleOCR-VL-1.5-GGUF,hf://beclab/PP-DocLayoutV3_onnx
{{- end -}}

{{- define "paddleocrhybrid.modelName" -}}paddle-hybrid{{- end -}}

{{- /* Redis URL from Olares middleware (.Values.redis). */ -}}
{{- define "paddleocrhybrid.redisURL" -}}
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
