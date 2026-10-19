{{- define "embeddinggemma2.embedTag" -}}b4727a7-onnx-cpu{{- end -}}
{{- define "embeddinggemma2.llmInitTag" -}}3c3f14b{{- end -}}
{{- define "embeddinggemma2.modelRepo" -}}onnx-community/embeddinggemma-2-ONNX{{- end -}}
{{- define "embeddinggemma2.modelRevision" -}}daa72c51243991dfcaf9f9137d2c573d8f7790c0{{- end -}}
{{- define "embeddinggemma2.logicalModelName" -}}embeddinggemma-2{{- end -}}
{{- define "embeddinggemma2.modelId" -}}embeddinggemma-2{{- end -}}

{{- define "embeddinggemma2.modelSource" -}}
{{- $repo := include "embeddinggemma2.modelRepo" . -}}
{{- $rev := include "embeddinggemma2.modelRevision" . -}}
hf://{{ $repo }} --revision {{ $rev }} --include onnx/model.onnx --include onnx/model.onnx_data --include onnx/vision_encoder.onnx --include onnx/vision_encoder.onnx_data --include onnx/audio_encoder.onnx --include onnx/audio_encoder.onnx_data --include tokenizer.json --include tokenizer_config.json --include config.json --include config_sentence_transformers.json --include preprocessor_config.json --include processor_config.json --include chat_template.jinja --include README.md --subdir onnx
{{- end -}}
