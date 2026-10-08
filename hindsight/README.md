# Hindsight for Olares

Hindsight 0.6.2 (MIT), packaged with separate API and web control-plane services.
Upstream: https://github.com/vectorize-io/hindsight

## Configure models

Install Olares Router, configure working chat and embedding routes, and set
`HINDSIGHT_API_LLM_BASE_URL` to its OpenAI-compatible shared entrance with `/v1`.
The default URL is the Router shared entrance. Both model types use this endpoint.
Set `HINDSIGHT_API_LLM_MODEL` and `HINDSIGHT_API_EMBEDDINGS_MODEL` to your routes
(defaults `default-chat` and `default-embedding`). Supply an API key when required.
Alternatively use an OpenAI-compatible provider serving both model types.
The slim API image does not bundle embedding or chat models. Embedding batch size
is one for compatibility with endpoints that accept one input per request.

## Connect Hermes

Open the Hindsight control plane and create or select a memory bank. Configure
the API entrance access policy so your client can reach it, then use its HTTPS
URL as the Hindsight API base URL in Hermes memory-provider setup. Choose the
existing remote/local-service connection and enter the bank ID. A standalone
Hindsight server needs the client package in Hermes, not hindsight-all.

After disabling automatic recall/retain in Hermes, explicitly ask it to use
`hindsight_retain` to store facts, `hindsight_recall` to retrieve them, and
`hindsight_reflect` to reason over memories. Availability depends on the tools
enabled in your Hermes configuration. Confirm a retain by recalling the fact
from the same bank rather than relying only on the chat reply.

The web entrance is private; the API entrance is internal by default. Do not
assume the cluster Service is reachable across applications. Configure the
entrance for your intended client and keep credentials out of prompts and Git.

## Processing and storage

PostgreSQL middleware with pgvector persists memory banks. Chat generation,
fact extraction, embeddings and background processing depend on the selected
model service. Small CPU models or a route allowing only one request at a time
can make retain/reflect slow or fail during concurrent work. Plan model capacity
before enabling automatic memory on every chat turn.

Chart version: 0.0.13. See TESTING.md for validation limits.
