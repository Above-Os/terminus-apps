# DAMO RADAR for Olares

Research inference for contrast-enhanced abdominal CT, packaged with a private web interface. Upload a NIfTI volume (`.nii` or `.nii.gz`) or run the official example, then download the 146 prediction scores and job logs. Predictions are research outputs, not clinical diagnoses or lesion contours.

## Runtime

- Chart: `0.0.6`; image: `riddlemeteng/damoradar:0.0.4`.
- Olares `>=1.12.6-0`, Linux amd64, NVIDIA GPU. No ARM or CPU inference support is declared.
- Model assets are downloaded by the initializer into the shared Hugging Face cache in `appCommon`. Uploaded inputs and job results persist in `appData`.
- Hugging Face endpoint and token come from Olares user settings. No credentials or model weights are embedded in the chart or image.
- Free GPU memory before starting inference. The chart requests 22 GiB; it does not stop other model applications automatically. Each inference subprocess releases its GPU allocations when it exits.

## Upstream and licensing

The original GitHub repository returned 404 during packaging. This image uses the authors' [Zenodo v3 source archive](https://zenodo.org/records/21504519), verified against MD5 `3aca73a254de7618a9dd7e2cfccfd4bb`.

Model weights come from [radar-generalist/RADAR](https://huggingface.co/radar-generalist/RADAR), pinned to revision `dd3a1086d471afbcf1f52b38f9392deed8e82ed7`. The upstream code is Apache-2.0; model weights are CC BY-NC-SA 4.0. The noncommercial restriction applies to the weights.

Example data, reference scores and precomputed text embeddings come from the authors' [Zenodo v2 archive](https://zenodo.org/records/21271172). The initializer verifies individual asset SHA-256 hashes. On an empty cache, it downloads the full archive and verifies its advertised MD5 before extracting assets.

The runtime adapts asset paths and checkpoint loading, uses zero DataLoader workers, and permits only five missing parameters from the unused text prediction head. It retains FP32 inference, the original preprocessing, and the original sliding-window settings.

## Validation and draft follow-ups

Validated on Olares 1.12.7 with an RTX 5090 Laptop GPU (23.88 GiB VRAM): image pull, application startup, private web access, and inference on the official `512 x 512 x 368` example.

- All 146 scores were finite and present.
- Inference: 3.09 seconds; complete job: 7.60 seconds.
- Peak CUDA allocation: 11.58 GiB; reservation: 17.62 GiB.
- Mean absolute difference from the authors' reference: 0.00005562; maximum: 0.00642169. Results are not bit-identical.

Only one example has been tested; larger volumes and clinical validity have not been evaluated. The tested installation had prepopulated assets, so a complete first installation with an empty cache still needs verification. CPU requests remain at the tested 25m setting and may provide limited performance under contention. Olares 1.12.6 has not been tested separately.

The default icon is a placeholder. Application-specific artwork and publication of the container build sources remain follow-ups for this draft. The separate OHIF experiment is not included in this chart.
