{{- define "jevk5v3.engineImage" -}}docker.io/beclab/systemone-engine:v0.1.0-jevk5-cuda12.8-amd64{{- end -}}
{{- define "jevk5v3.llmInitImage" -}}docker.io/beclab/llm-init:system-one-b6a30bd-amd64{{- end -}}
{{- define "jevk5v3.modelName" -}}jevk5{{- end -}}
{{- define "jevk5v3.modelRepo" -}}alibiserikbay/JevK5{{- end -}}
{{- define "jevk5v3.modelRevision" -}}c4f7fdb3aeab5582336406e78d3bef11bf98833d{{- end -}}
{{- define "jevk5v3.runtimeRevision" -}}85238d7be5527370c43206fe54cd752eb3134c1b{{- end -}}
{{- define "jevk5v3.runStatePath" -}}{{ printf "%s/llm-init-run/%s" .Values.userspace.appCache .Release.Name }}{{- end -}}

