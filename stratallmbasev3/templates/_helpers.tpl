{{- /* llmbase.gpuMiB: normalize a GPU-memory quantity to a BARE MiB integer for
       HAMi's nvidia.com/gpumem. Its base unit is MiB and the value MUST be a
       plain integer — a Mi/Gi suffix is misread by the scheduler (e.g. "6144Mi"
       -> 6442450944). Accepts 8Gi / 8G / 8192Mi / 8192M / 8192 and returns MiB.
       Usage: {{ include "llmbase.gpuMiB" ($oe.STRATA_REQUIRED_GPU_MEMORY | default "4096") }} */ -}}
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

{{- define "strata.hfPath" -}}
/cache/hf/hub
{{- end -}}

{{- define "strata.runStateSubpath" -}}
{{- /* Readiness, model_path and model-spec belong to one model identity.
       Include the source and public name so a different model cannot inherit
       an old ready sentinel or model card. Keep ENGINE_ARGS out: tuning must
       preserve the card for the same weights. Keep this byte-identical to the
       standalone Strata apps so a clone upgraded from one keeps its run state. */ -}}
{{- $oe := .Values.olaresEnv | default dict -}}
{{- $identity := list ($oe.MODEL_NAME | default "") ($oe.MODEL_SOURCE | default "") | toJson | sha256sum | trunc 20 -}}
{{- printf "llm-init-run/%s/model-%s" .Release.Name $identity -}}
{{- end -}}

{{- define "strata.runStateHostPath" -}}
{{- $us := .Values.userspace | default dict -}}
{{- printf "%s/%s" ($us.appCommon | default "/olares/common") (include "strata.runStateSubpath" .) -}}
{{- end -}}

{{- define "strata.dataHostPath" -}}
{{- $us := .Values.userspace | default dict -}}
{{- printf "%s/huggingface/strata-data/%s" ($us.appCommon | default "/olares/common") .Release.Name -}}
{{- end -}}

{{- /* strata.resources: engine resources as JSON; an env value wins over the
       chart default in values.yaml strata.defaults. */ -}}
{{- define "strata.resources" -}}
{{- $oe := .Values.olaresEnv | default dict -}}
{{- $d := (.Values.strata | default dict).defaults | default dict -}}
{{- dict
      "cpuRequest" (toString ($oe.STRATA_CPU_REQUEST | default $d.cpuRequest | default "200m"))
      "memoryRequest" (toString ($oe.STRATA_MEMORY_REQUEST | default $d.memoryRequest | default "2Gi"))
      "cpuLimit" (toString ($oe.STRATA_CPU_LIMIT | default $d.cpuLimit | default "8"))
      "memoryLimit" (toString ($oe.STRATA_MEMORY_LIMIT | default $d.memoryLimit | default "35Gi"))
      "gpuMemory" (toString ($oe.STRATA_REQUIRED_GPU_MEMORY | default $d.gpuMemory | default "4096"))
    | toJson -}}
{{- end -}}

{{- /* strata.build: the setup.py family and build as JSON, read from the files that
       MODEL_SOURCE names in the official repositories (setup.py's catalog).
       values.yaml strata.family / strata.model name the build for a source this
       table does not know, such as a mirror repository. Rule: repository, file
       pattern (the build is group 1 or 2), family, and a fixed build when the
       repository holds only one. */ -}}
{{- define "strata.build" -}}
{{- $oe := .Values.olaresEnv | default dict -}}
{{- $s := .Values.strata | default dict -}}
{{- $gsq := `^(?:([A-Z0-9_]+)/\*?|(?:.*/)?%sQwen3\.8-Flash-Next-GSQ-RCO-([A-Z0-9_]+)-[0-9]{5}-of-[0-9]{5}\.gguf)$` -}}
{{- $rules := list
      (list "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF" (printf $gsq "") "qwen")
      (list "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF" (printf $gsq "") "coder")
      (list "ukisai/Swift-1.5-Qwen3.8-Flash-Next-GSQ-RCO-GGUF" (printf $gsq "Swift-") "swift")
      (list "unsloth/Qwen3.8-Flash-Next-GGUF" `^(?:((?:UD-)?[A-Z0-9_]+)/\*?|(?:.*/)?Qwen3\.8-Flash-Next-((?:UD-)?[A-Z0-9_]+)-[0-9]{5}-of-[0-9]{5}\.gguf)$` "unsloth")
      (list "agentionai/Qwen3.8-Flash-Next-Gyro-GGUF" `^(?:.*/)?Qwen3\.8-Flash-Next-(Gyro-[SM])-TQ[0-9]_0\.gguf$` "gyro")
      (list "Maximilian228/Qwen3.8-Flash-Next-NVFP4-GPTQ-Strata" `.*` "nvfp4" "NVFP4")
      (list "Maximilian228/Qwen3.8-Flash-Next-NVIDIA-NVFP4-Strata" `.*` "nvfp4" "NVFP4-NVIDIA")
      (list "nvidia/Qwen3.8-Flash-Next-FP4-Local" `.*` "nvfp4" "NVFP4-QAD")
      (list "unsloth/Qwen3.6-35B-A3B-MTP-GGUF" `^(?:.*/)?Qwen3\.6-35B-A3B-((?:UD-)?Q[0-9]_[A-Z0-9_]+)\.gguf$` "qwen36")
      (list "strata-engine/Hy4-Flash-Strata" `^(?:.*/)?Hy4-Flash-(SQ-[0-9]+)\.strata$` "hy4-flash")
      (list "strata-engine/Inkling-2-Mini-Strata" `^(?:.*/)?Inkling-2-Mini-(SQ-[0-9]+)\.strata$` "inkling-2-mini")
      (list "unsloth/Inkling-2-Mini-GGUF" `^(?:.*/)?Inkling-2-Mini-(UD-[A-Z0-9_]+)\.gguf$` "inkling-2-mini") -}}
{{- $source := $oe.MODEL_SOURCE | default "" | trim -}}
{{- $found := dict -}}
{{- range $segment := splitList "," $source -}}
{{- $seg := trim $segment -}}
{{- $repo := regexReplaceAll `^hf://([^ ]+).*$` $seg "${1}" -}}
{{- $rev := "" -}}
{{- if regexMatch `--revision +[^ ]+` $seg -}}
{{- $rev = regexReplaceAll `^.*--revision +([^ ]+).*$` $seg "${1}" -}}
{{- end -}}
{{- $files := list -}}
{{- range regexFindAll `--include +[^ ]+` $seg -1 -}}
{{- $files = append $files (regexReplaceAll `^--include +` . "") -}}
{{- end -}}
{{- if not $files -}}{{- $files = list "" -}}{{- end -}}
{{- range $rule := $rules -}}
{{- if eq (index $rule 0) $repo -}}
{{- range $file := $files -}}
{{- if regexMatch (index $rule 1) $file -}}
{{- $build := "" -}}
{{- if gt (len $rule) 3 -}}
{{- $build = index $rule 3 -}}
{{- else -}}
{{- $build = regexReplaceAll (index $rule 1) $file "${1}${2}" -}}
{{- end -}}
{{- /* setup.py's UD-IQ4_XS-v31 is the four-shard UD-IQ4_XS at the v3.1 revision. */ -}}
{{- if and (eq (index $rule 2) "unsloth") (eq $build "UD-IQ4_XS") (or (contains "-of-00004" $file) (eq $rev "d96201194f103c906994f283f504209dc8d2a10c")) -}}
{{- $build = "UD-IQ4_XS-v31" -}}
{{- end -}}
{{- $_ := set $found (printf "%s %s" (index $rule 2) $build) true -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- $named := keys $found | sortAlpha -}}
{{- if gt (len $named) 1 -}}
{{- fail (printf "MODEL_SOURCE names files of more than one Strata build (%s); list the files of one build" (join ", " $named)) -}}
{{- end -}}
{{- $family := $oe.STRATA_FAMILY | default $s.family | default "" | trim -}}
{{- $model := $oe.STRATA_MODEL | default $s.model | default "" | trim -}}
{{- if $named -}}
{{- $pair := splitList " " (first $named) -}}
{{- if and (or $family $model) (or (ne $family (index $pair 0)) (ne $model (index $pair 1))) -}}
{{- fail (printf "strata.family / strata.model %s / %s do not match MODEL_SOURCE, which names %s / %s" $family $model (index $pair 0) (index $pair 1)) -}}
{{- end -}}
{{- $family = index $pair 0 -}}
{{- $model = index $pair 1 -}}
{{- else if and $source (not (and $family $model)) -}}
{{- fail "MODEL_SOURCE names no file of an official Strata build; set strata.family and strata.model in values.yaml" -}}
{{- end -}}
{{- dict "family" $family "model" $model | toJson -}}
{{- end -}}

{{- /* strata.cpuMilli: "8" / "200m" -> millicores, for comparing request and limit. */ -}}
{{- define "strata.cpuMilli" -}}
{{- $c := trim . -}}
{{- if hasSuffix "m" $c -}}{{- int (trimSuffix "m" $c) -}}
{{- else -}}{{- mul (int $c) 1000 -}}{{- end -}}
{{- end -}}

{{- /* strata.memMiB: "35Gi" / "512Mi" -> MiB, for comparing request and limit. */ -}}
{{- define "strata.memMiB" -}}
{{- $m := trim . -}}
{{- if hasSuffix "Gi" $m -}}{{- mul (int (trimSuffix "Gi" $m)) 1024 -}}
{{- else -}}{{- int (trimSuffix "Mi" $m) -}}{{- end -}}
{{- end -}}

{{- /* strata.validate: cross-field rules the manifest regexes cannot express.
       Keep the build table in step with strata.build and setup.py. */ -}}
{{- define "strata.validate" -}}
{{- $oe := .Values.olaresEnv | default dict -}}
{{- $builds := dict
      "qwen" (list "Q2_0" "IQ2_XS" "IQ3_XXS" "IQ3_S")
      "swift" (list "Q2_0" "IQ2_XS" "IQ3_XXS" "IQ3_S")
      "coder" (list "IQ1_M")
      "unsloth" (list "UD-IQ4_XS" "UD-Q4_K_XL" "UD-Q5_K_XL" "UD-Q6_K_XL" "Q8_0" "UD-IQ1_M" "UD-Q2_0" "UD-IQ2_XS" "UD-Q2_K_XL" "UD-IQ3_XXS" "UD-Q3_K_XL" "UD-IQ4_XS-v31")
      "gyro" (list "Gyro-S" "Gyro-M")
      "nvfp4" (list "NVFP4" "NVFP4-NVIDIA" "NVFP4-QAD")
      "qwen36" (list "UD-Q4_K_XL" "UD-Q6_K_XL" "Q8_0")
      "hy4-flash" (list "SQ-64" "SQ-96" "SQ-128")
      "inkling-2-mini" (list "SQ-20" "SQ-15" "SQ-10" "UD-Q8_K_XL" "UD-Q4_K_XL" "UD-Q4_K_M" "UD-IQ4_XS" "UD-Q3_K_XL" "UD-IQ3_XXS" "UD-Q2_K_XL" "UD-IQ2_XXS" "UD-IQ1_M" "UD-IQ1_S") -}}
{{- $build := include "strata.build" . | fromJson -}}
{{- $family := $build.family -}}
{{- $model := $build.model -}}
{{- if and $family $model -}}
{{- if not (hasKey $builds $family) -}}
{{- fail (printf "Strata family %q is not one of: %s" $family (keys $builds | sortAlpha | join ", ")) -}}
{{- end -}}
{{- if not (has $model (index $builds $family)) -}}
{{- fail (printf "Strata build %q is not a %s build (one of: %s)" $model $family (index $builds $family | join ", ")) -}}
{{- end -}}
{{- end -}}
{{- $supports := splitList "," ($oe.MODEL_SUPPORTS | default "") | compact -}}
{{- if and (has "none" $supports) (gt (len $supports) 1) -}}
{{- fail "MODEL_SUPPORTS: None cannot be combined with Vision, Tools, or Thinking" -}}
{{- end -}}
{{- $efforts := splitList "," ($oe.MODEL_REASONING_EFFORT | default "") | compact -}}
{{- $effortDefault := $oe.MODEL_REASONING_EFFORT_DEFAULT | default "" | trim -}}
{{- if and $effortDefault $efforts (not (has $effortDefault $efforts)) -}}
{{- fail (printf "MODEL_REASONING_EFFORT_DEFAULT %q is not one of MODEL_REASONING_EFFORT (%s)" $effortDefault (join "," $efforts)) -}}
{{- end -}}
{{- $res := include "strata.resources" . | fromJson -}}
{{- $memReq := $res.memoryRequest -}}
{{- $memLim := $res.memoryLimit -}}
{{- if gt (int (include "strata.memMiB" $memReq)) (int (include "strata.memMiB" $memLim)) -}}
{{- fail (printf "STRATA_MEMORY_REQUEST %s is above STRATA_MEMORY_LIMIT %s" $memReq $memLim) -}}
{{- end -}}
{{- if gt (int (include "strata.cpuMilli" $res.cpuRequest)) (int (include "strata.cpuMilli" $res.cpuLimit)) -}}
{{- fail (printf "STRATA_CPU_REQUEST %s is above STRATA_CPU_LIMIT %s" $res.cpuRequest $res.cpuLimit) -}}
{{- end -}}
{{- /* An upgrade keeps an installed app's old env regex, so the ceilings are
       checked here as well. */ -}}
{{- $max := (.Values.strata | default dict).max | default dict -}}
{{- $maxCpu := toString ($max.cpu | default "20") -}}
{{- $maxMem := toString ($max.memory | default "84Gi") -}}
{{- $maxGpu := toString ($max.gpuMemory | default "23Gi") -}}
{{- if gt (int (include "strata.cpuMilli" $res.cpuLimit)) (int (include "strata.cpuMilli" $maxCpu)) -}}
{{- fail (printf "STRATA_CPU_LIMIT %s is above the %s-core ceiling" $res.cpuLimit $maxCpu) -}}
{{- end -}}
{{- if gt (int (include "strata.memMiB" $memLim)) (int (include "strata.memMiB" $maxMem)) -}}
{{- fail (printf "STRATA_MEMORY_LIMIT %s is above the %s ceiling" $memLim $maxMem) -}}
{{- end -}}
{{- if gt (int (include "llmbase.gpuMiB" $res.gpuMemory)) (int (include "llmbase.gpuMiB" $maxGpu)) -}}
{{- fail (printf "STRATA_REQUIRED_GPU_MEMORY %s is above the %s ceiling" $res.gpuMemory $maxGpu) -}}
{{- end -}}
{{- end -}}

{{- /* Vision is on when the clone selects the Vision capability. */ -}}
{{- define "strata.vision" -}}
{{- $oe := .Values.olaresEnv | default dict -}}
{{- $supports := $oe.MODEL_SUPPORTS | default "" -}}
{{- if contains "vision" $supports -}}yes{{- else -}}no{{- end -}}
{{- end -}}
