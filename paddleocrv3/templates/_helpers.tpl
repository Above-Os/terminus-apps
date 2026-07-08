{{- /* Olares accelerator mode: nvidia only (v3). */ -}}
{{- define "paddleocrv3.gpuType" -}}
{{- $gpuObj := .Values.GPU | default dict -}}
{{- $gpuType := .Values.gpu | default "" -}}
{{- if not $gpuType -}}
{{- $gpuType = $gpuObj.Type | default "nvidia" -}}
{{- end -}}
{{- $gpuType -}}
{{- end -}}

{{- /* RTX 50 / Blackwell (sm120) detection — same rules as paddleocr v2. */ -}}
{{- define "GPU.getGPUInfo" -}}
{{- $gpuModel := "" -}}
{{- $gpuModelName := "" -}}
{{- $is50Series := "false" -}}
{{- if .Values.nodes -}}
  {{- range $nodeIndex, $node := .Values.nodes -}}
    {{- if eq $nodeIndex 0 -}}
      {{- with $node -}}
        {{- if .GPUS -}}
          {{- range $gpuIndex, $gpu := .GPUS -}}
            {{- if eq $gpuIndex 0 -}}
              {{- with $gpu -}}
                {{- $gpuModel = .Model -}}
                {{- $gpuModelName = .ModelName -}}
                {{- $modelUpper := upper .Model -}}
                {{- $modelNameUpper := upper .ModelName -}}
                {{- $isRTX50XX := and (hasPrefix "50" $modelUpper) (not (hasPrefix "500" $modelUpper)) (ne "50" $modelUpper) -}}
                {{- $isRTX50XX = or $isRTX50XX (and (contains "RTX 50" $modelNameUpper) (not (contains "RTX 5000" $modelNameUpper)) (not (contains "QUADRO" $modelNameUpper))) -}}
                {{- if $isRTX50XX -}}
                  {{- $is50Series = "true" -}}
                {{- end -}}
              {{- end -}}
            {{- end -}}
          {{- end -}}
        {{- end -}}
      {{- end -}}
    {{- end -}}
  {{- end -}}
{{- end -}}
{{- dict "gpuModel" $gpuModel "gpuModelName" $gpuModelName "is50Series" $is50Series | toJson -}}
{{- end -}}

{{- /* Normalize GPU memory to bare MiB for HAMi nvidia.com/gpumem. */ -}}
{{- define "paddleocrv3.gpuMiB" -}}
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

{{- /* Offline GPU image: sm120 for RTX 50, else CUDA 12.6 route. */ -}}
{{- define "paddleocrv3.engineImage" -}}
{{- $gpuInfo := include "GPU.getGPUInfo" . | fromJson -}}
{{- if eq $gpuInfo.is50Series "true" -}}
docker.io/beclab/bleachzou-paddleocr3.4-nividia-gpu-sm120-offline:0.0.1
{{- else -}}
docker.io/beclab/bleachzou-paddleocr3.4-nividia-gpu-offline:0.0.1
{{- end -}}
{{- end -}}
