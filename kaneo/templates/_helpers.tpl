{{- define "kaneo.secretName" -}}
{{- printf "%s-secrets" .Release.Name -}}
{{- end -}}

{{- define "kaneo.authSecret" -}}
{{- $secretName := include "kaneo.secretName" . -}}
{{- $existing := lookup "v1" "Secret" .Release.Namespace $secretName -}}
{{- if and $existing $existing.data (index $existing.data "AUTH_SECRET") -}}
{{- index $existing.data "AUTH_SECRET" | b64dec -}}
{{- else -}}
{{- randAlphaNum 64 -}}
{{- end -}}
{{- end -}}
