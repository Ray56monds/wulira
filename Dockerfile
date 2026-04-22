FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg git && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 user
WORKDIR /app

RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir deep-translator && \
    pip install --no-cache-dir --upgrade yt-dlp && \
    pip install --no-cache-dir pytubefix gallery-dl && \
    pip install --no-cache-dir bgutil-ytdlp-pot-provider && \
    pip install --no-cache-dir transformers librosa

RUN python -c "import whisper; whisper.load_model('base')"

# This ARG busts the cache for COPY on every push
ARG CACHEBUST=1
COPY . .
RUN chown -R user:user /app

USER user

ENV ENV=production \
    API_HOST=0.0.0.0 \
    API_PORT=7860 \
    LOG_LEVEL=INFO \
    CORS_ORIGINS=* \
    MAX_JOBS_IN_MEMORY=50 \
    JOB_TIMEOUT_SECONDS=3600

EXPOSE 7860

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
