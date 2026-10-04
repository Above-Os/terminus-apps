# Ollama Shared v3

`ollamasharedv3` runs a single shared Ollama 0.33.1 daemon in the
`ollamasharedv3-shared` namespace. Model data persists in the application's
private `appData` directory.

## Pull the Q4 models

Open the **Ollama Terminal** entrance and run:

```sh
ollama pull qwen3.8:27b-q4_K_M
ollama pull gemma4:12b-it-q4_K_M
ollama list
```

These are explicit Q4_K_M tags; do not replace them with floating aliases.

## Router

Create a manual provider named `ollamashared`, using the Router provider type
**OpenAI-API-compatible**, with this Base URL:

```text
http://e805eb801.yaotest005.olares.com/v1
```

Select **Test** and confirm that the provider reports two models before saving
it.

Validate the provider and sync models. The qualified model IDs are:

```text
ollamashared/qwen3.8:27b-q4_K_M
ollamashared/gemma4:12b-it-q4_K_M
```

Do not pin `default-chat`; select each qualified model explicitly in Lares.

Set both models to a 32768-token context and declare vision, function calling,
tool choice, and reasoning support. Also declare reasoning-effort support on
Qwen.

## Runtime policy

The environment follows the proven `ollamav2` tuning (`OLLAMA_ORIGINS`, flash
attention, and llama.cpp fit controls) and adds
`OLLAMA_MAX_LOADED_MODELS=1`. Parallelism, keep-alive, context length, and KV
cache type retain the Ollama 0.33.1 defaults.
