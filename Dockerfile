FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    CAMELTOOLS_DATA=/tmp/camel_tools \
    MORPH_DATA_DIR=/app/data \
    PORT=3000 \
    MCP_PATH=/api/open-conjugator-mcp

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY requirements-morphology.txt ./
COPY src ./src
RUN pip install --no-cache-dir . \
    && pip install --no-cache-dir --no-deps -r requirements-morphology.txt

COPY scripts/prepare_data.py ./scripts/prepare_data.py
RUN python scripts/prepare_data.py --data-dir /app/data --cache-dir /tmp/morph-cache \
    && rm -rf /tmp/morph-cache

RUN useradd --create-home --uid 10001 mcp \
    && chown -R mcp:mcp /app
USER mcp

EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','3000')+'/health', timeout=3)"

CMD ["python", "-m", "open_conjugator_mcp", "--transport", "http"]
