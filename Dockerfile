FROM python:3.11-slim

WORKDIR /app

# torch/OpenMP default to one thread per CPU core, which adds real memory
# overhead per thread -- on a constrained container we only ever process
# one request's embeddings at a time anyway, so extra threads buy nothing.
# Must be set before torch is ever imported, hence here rather than in
# application code.
ENV OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false

# Install the CPU-only torch build first. The default Linux pip install
# pulls a CUDA-enabled build -- ~3GB of unused NVIDIA packages on a
# container with no GPU, plus real memory overhead from CUDA-availability
# checks torch runs at import time. Installing this first means
# sentence-transformers' torch dependency below is already satisfied by
# the lean build and pip never swaps it for the default CUDA one.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
