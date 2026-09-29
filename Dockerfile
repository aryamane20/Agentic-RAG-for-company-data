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

# Pre-download and cache the embedding model at build time, not runtime.
# Render's container filesystem is ephemeral -- with no persistent cache,
# every deploy would otherwise hit HuggingFace's network on first boot,
# and that download (on top of loading the model itself) is what was
# pushing memory over the 512Mi limit during startup. Baking it into the
# image means startup loads straight from local disk, no network
# involved, and cold starts are faster too.
RUN python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Only now, after the model is cached above -- huggingface_hub otherwise
# does a revision-check network call against HuggingFace on every load
# even when the files are already cached. Offline mode skips that and
# reads straight from the cache populated by the RUN step above.
ENV HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

CMD ["./docker-entrypoint.sh"]
