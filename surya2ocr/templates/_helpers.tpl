{{- /* surya2ocr.gpuMiB: normalize GPU memory to bare MiB int for nvidia.com/gpumem. */ -}}
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

{{- define "surya2ocr.llmInitTag" -}}v1.5.0{{- end -}}
{{- define "surya2ocr.ocrAdapterImage" -}}docker.io/beclab/ocr-adapter:v0.0.2{{- end -}}
{{- define "surya2ocr.llamacppImage" -}}docker.io/beclab/ggml-org-llama.cpp:server-cuda12-b10143{{- end -}}

{{- /* Comma dual-source, each one --include (single-file hf path).
       Avoids one hf:// with two --include leaving snapshot without main GGUF.
       Also skips tokenizer/assets in the same HF repo. */ -}}
{{- define "surya2ocr.modelSource" -}}
hf://datalab-to/surya-ocr-2-gguf --include surya-2.gguf,hf://datalab-to/surya-ocr-2-gguf --include surya-2-mmproj.gguf
{{- end -}}

{{- define "surya2ocr.modelName" -}}surya2{{- end -}}

{{- /* Redis URL from Olares middleware (.Values.redis). */ -}}
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
