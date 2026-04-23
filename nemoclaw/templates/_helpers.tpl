{{/*
Browser origin for OpenClaw web UI allowlist (CHAT_UI_URL).
Olares sets domain per entrance name (see OlaresManifest entrances[].name). Web UI entrance is "webtui"
→ Values.domain.webtui (comma-separated hosts, first wins). Legacy: domain.nemoclaw.
*/}}
{{- define "nemoclaw.chatUiUrl" -}}
{{- if .Values.olaresEnv.CHAT_UI_URL -}}
{{- .Values.olaresEnv.CHAT_UI_URL -}}
{{- else if and .Values.domain .Values.domain.webtui -}}
{{- $hosts := splitList "," .Values.domain.webtui -}}
{{- if gt (len $hosts) 0 -}}
{{- $h := trim (index $hosts 0) -}}
{{- if ne $h "" -}}
https://{{ $h }}
{{- end -}}
{{- end -}}
{{- else if and .Values.domain .Values.domain.nemoclaw -}}
{{- $hosts := splitList "," .Values.domain.nemoclaw -}}
{{- if gt (len $hosts) 0 -}}
{{- $h := trim (index $hosts 0) -}}
{{- if ne $h "" -}}
https://{{ $h }}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
