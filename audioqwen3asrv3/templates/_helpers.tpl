{{- /* llmbase.gpuMiB: 8Gi/8G/8192Mi/8192M/8192 -> a BARE MiB integer, since HAMi misreads a suffix. */ -}}
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

{{- /* Both Deployments must agree on this render's cleanup, even after reinstall. */ -}}
{{- define "audio.runStateGeneration" -}}
{{- if not (hasKey .Values "_audioRunStateGeneration") -}}
{{- $_ := set .Values "_audioRunStateGeneration" (randAlphaNum 32) -}}
{{- end -}}
{{- .Values._audioRunStateGeneration -}}
{{- end -}}
