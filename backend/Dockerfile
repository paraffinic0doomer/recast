# The API ships as a container for one reason: FFmpeg.
#
# Metadata probing, audio extraction, clip cutting, the 9:16 reframe and the
# caption burn-in all shell out to ffmpeg/ffprobe. Render's native Python
# runtime does not provide them, so a Docker image is the only way to get a
# working pipeline rather than a service that fails on the first upload.
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so code edits don't invalidate the pip layer.
COPY requirements-deploy.txt ./
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY app ./app
COPY scripts ./scripts

# Render mounts the persistent disk over this path. Creating it here keeps the
# image runnable locally too, where there is no disk to mount.
RUN mkdir -p /app/storage

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

# sh -c to expand $PORT (Render assigns it per instance), and `exec` so uvicorn
# replaces the shell as PID 1. Without exec, SIGTERM on redeploy would go to the
# shell and never reach uvicorn, so shutdown would be a hard kill.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
