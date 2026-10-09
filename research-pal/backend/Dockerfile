# Docker image for Hugging Face Spaces (also works on any Docker host).
FROM python:3.11-slim

# Hugging Face runs the container as user 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    DATA_DIR=/home/user/data \
    PYTHONUNBUFFERED=1
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the embedding model now, so the first upload does not wait for it.
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as E; E()(['warm up'])"

COPY --chown=user app ./app
RUN mkdir -p /home/user/data

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
