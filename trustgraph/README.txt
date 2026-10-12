TrustGraph for Olares

Core and Docling: 2.10.10; Web UI: 2.3.2; Chart: 0.1.16.

Install Router and start chat, embedding, and reranking models. Supply an OpenAI-compatible base URL ending in /v1 and a Router API key at installation. API credentials are supplied through Olares installation values and must not be committed.

The default flow pins Olares/embeddinggemma-300m (768 dimensions), with default-chat and default-rerank. Jina CLIP v2 collections require a matching flow and separate collection. Existing 384-dimensional collections use the legacy-minilm flow.

The initial TrustGraph API key is generated in the iam-bootstrap-token Kubernetes Secret. An authorized administrator can retrieve it from Control Hub and use API Key login. Username/password initialization is not automatically performed.

Multipart upload compatibility stages browser transport chunks in the application's MinIO bucket and streams the final object with compliant S3 parts. Successful completion and cancellation clean up staged chunks. Abandoned sessions currently have no automatic cleanup policy. Restart unfinished uploads created before this patch.

Validated on an amd64 Olares 1.12.7 instance: text/PDF/DOCX ingestion, vector retrieval, Document RAG, Graph RAG, graph/SPARQL access, CRUD and API-key authentication. Multipart cases cover 3 MiB, 13 MiB plus 17 bytes, reconnect/resume, duplicate/out-of-order chunks, invalid chunk rejection, cancellation, SHA256 integrity, and a large PDF through downstream RAG.

Limitations: Graph RAG can include irrelevant provenance sources. Username/password login, incorrect-password rejection, JWT identity and WebSocket authentication are validated. Multi-step agent workflows are not validated. A clean-install regression and two historical-version migration matrix remain pending; this draft is for test-market smoke testing.

Authentication proxy preserves upstream HTTP status codes and Authorization headers. The first administrator password is managed through authenticated IAM reset-password/change-password operations, rather than direct database writes.

IAM response translation preserves service errors so invalid credentials return HTTP 401, with no JWT issued.
