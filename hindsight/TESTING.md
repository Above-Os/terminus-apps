# Validation

- Olares test system: 1.12.7, amd64; Hindsight chart 0.0.12 is running.
- HTTPS API health from Hermes returned healthy / database connected.
- Retain and recall were exercised through Hermes; recall retrieved the stored Olares fact.
- Embedding batch size one was deployed for the current single-input endpoint.
- Background processing can encounter 503 responses when the model route is busy; this draft does not claim that model capacity issue is resolved.
- Chart 0.0.13 changes listing metadata, assets and documentation only; runtime templates match the running chart.
- Both beclab runtime image tags expose linux/amd64 and linux/arm64 manifests. ARM64 execution has not been tested on a node.
- Listing assets use the official mark and conceptual architecture diagrams, with no fabricated UI or Chinese text.
