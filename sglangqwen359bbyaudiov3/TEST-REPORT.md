# Thinking off by default — 1.0.3

The engine now starts with `--default-chat-template-kwargs {"enable_thinking":false}`.
The chart's `engineArgs` helper adds it unless `ENGINE_ARGS` already carries the
flag or the app serves embeddings. It is added there, not to the `ENGINE_ARGS`
default, because an upgrade keeps an installation's saved `ENGINE_ARGS`. A
request can still turn thinking on with `chat_template_kwargs`.

`MODEL_REASONING_EFFORT` and `MODEL_REASONING_EFFORT_DEFAULT` are removed.
llm-init then builds no `reasoning_effort` rule for a new card. Its overlay only
acts when the chart declares a ladder, so a card persisted by 1.0.2 keeps its
`none,high` rule (`internal/config/config_load_model.go`,
`overlayReasoningEffortRuleFromEnv`).

`ENGINE_ARGS` is rendered with `toJson` in both templates, because the new flag
carries double quotes.

## Why

Measured on pptest03 through Router against 1.0.2, with a one-sentence answer
and `max_tokens` 1024:

| Request | Time | Reasoning tokens | Answer |
| --- | --- | --- | --- |
| Default (thinking on) | 9.9 s | 1024 (the whole budget) | empty |
| `chat_template_kwargs.enable_thinking=false` | 0.17–0.22 s | 0 | complete |
| `reasoning_effort: "none"` | 0.37 s | 0 | complete |

Lares voice sessions on this model passed 36/50 live scenarios with thinking on
and 46–49/50 with it off (`scripts/voice-eval` in beclab/lares).

## Local checks

- `olares-cli chart lint`: passed under both owner installation scenarios,
  including the Helm dry-run render.
- The flag's value reaches SGLang intact: `wrappers/sglang.sh` word-splits
  `ENGINE_ARGS` without `eval`, and the JSON has no spaces.
- `--default-chat-template-kwargs` exists in the pinned image
  (`lmsysorg/sglang:v0.5.18-cu130`, `python3 -m sglang.launch_server --help`).

## Runtime checks pending deployment

This revision was not uploaded, installed or deployed. Still to check:

- After a new install and after an upgrade from 1.0.2: the engine command line
  carries the flag, and a request with no thinking parameters returns
  `reasoning_tokens: 0` and a complete reply.
- A request with `chat_template_kwargs.enable_thinking=true` still thinks.
- Router catalog: no `reasoning_effort` rule on a new card; an upgraded card
  keeps `none,high`.
