FROM node:24.11.0-bookworm-slim AS dashboard
WORKDIR /src/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ENV VITE_OLARES_AUTH=1
RUN npm run build

FROM ubuntu:24.04 AS engine
RUN apt-get update && apt-get install -y --no-install-recommends build-essential python3 ca-certificates curl && \
    curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb -o /tmp/cuda-keyring.deb && \
    dpkg -i /tmp/cuda-keyring.deb && apt-get update && \
    apt-get install -y --no-install-recommends cuda-nvcc-12-8 cuda-cudart-dev-12-8 libcublas-dev-12-8 && \
    rm -rf /var/lib/apt/lists/* /tmp/cuda-keyring.deb
ENV CUDA_HOME=/usr/local/cuda-12.8
RUN apt-get update && apt-get install -y --no-install-recommends cuda-profiler-api-12-8 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY c/ ./c/
# Explicit Blackwell architecture for the verified RTX 5090 target.
RUN make -C c -j2 install CUDA=1 CUDA_HOME=/usr/local/cuda-12.8 CUDA_ARCH=sm_120 ARCH=x86-64-v3 PREFIX=/usr/local DESTDIR=/stage

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3 libgomp1 ca-certificates nginx-light && rm -rf /var/lib/apt/lists/* && if ! getent group 1000 >/dev/null; then groupadd -g 1000 colibri; fi && if ! getent passwd 1000 >/dev/null; then useradd -u 1000 -g 1000 -m colibri; fi
# Ship the CUDA libraries used by the engines, rather than unrelated runtime
# libraries such as cuFFT/cuSPARSE. The GPU driver is supplied by Olares.
COPY --from=engine /usr/local/cuda-12.8/lib64/libcudart.so.12.* /usr/local/lib/
COPY --from=engine /usr/local/cuda-12.8/lib64/libcublas.so.12.* /usr/local/lib/
COPY --from=engine /usr/local/cuda-12.8/lib64/libcublasLt.so.12.* /usr/local/lib/
RUN for library in libcudart libcublas libcublasLt; do set -- /usr/local/lib/${library}.so.12.*; test -f "$1"; ln -s "$(basename "$1")" "/usr/local/lib/${library}.so.12"; ln -s "${library}.so.12" "/usr/local/lib/${library}.so"; done
COPY --from=engine /stage/usr/local/ /usr/local/
COPY --from=dashboard /src/web/dist /usr/local/libexec/colibri/web/dist
RUN ln -s ../libexec/colibri/web /usr/local/bin/web
COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md /usr/share/doc/colibri/
ENV HOME=/data/home PYTHONUNBUFFERED=1 LD_LIBRARY_PATH=/usr/local/lib NVIDIA_VISIBLE_DEVICES=all NVIDIA_DRIVER_CAPABILITIES=compute,utility
WORKDIR /data
USER 1000:1000
EXPOSE 8000
ENTRYPOINT ["python3", "/usr/local/bin/coli"]
CMD ["--help"]
