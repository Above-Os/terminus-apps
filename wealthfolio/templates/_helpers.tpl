{{/*
  Master key must stay stable: Wealthfolio encrypts the vault with it.
  Delete this Secret and upgrade to rotate; existing data will not decrypt.
*/}}
{{- define "wealthfolio.secretKey" -}}
{{- $existing := lookup "v1" "Secret" .Release.Namespace "wealthfolio-master-key" -}}
{{- if and $existing $existing.data (index $existing.data "WF_SECRET_KEY") -}}
{{- index $existing.data "WF_SECRET_KEY" | b64dec -}}
{{- else -}}
{{- randBytes 32 -}}
{{- end -}}
{{- end -}}
