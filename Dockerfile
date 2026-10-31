# The Aieva fog server.
#
#   docker build -t aieva-server .
#   docker run --rm -p 8000:8000 -e GEMINI_API_KEY=... aieva-server
#
# The server never stores the key in the image - it is read from the
# environment at runtime.

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The system packages that Matplotlib and Pillow need.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libgl1 libglib2.0-0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-server.txt

COPY aieva ./aieva
COPY server ./server
COPY docs ./docs

# The server does not need a display.
ENV MPLBACKEND=Agg \
    PYTHONPATH=/app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
