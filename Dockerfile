# Generic image: framework + headless Chromium + one site directory. Build from the repo root:
#   docker build --build-arg SITE_DIR=servers/<site> -t <site>-mcp:local .
# The site directory must contain site.py exporting SITE. servers/<site>/compose.yaml does this.
FROM python:3.12-slim-bookworm
ARG SITE_DIR=servers/wikipedia
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browsers JEV_STATE_DIR=/data \
    CHROMIUM_SANDBOX=0
WORKDIR /app
RUN pip install --no-cache-dir uv==0.11.6
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project && \
    .venv/bin/playwright install --with-deps --only-shell chromium && \
    rm -rf /var/lib/apt/lists/* && chmod -R a+rX /opt/browsers
COPY src ./src
RUN uv sync --frozen --no-dev && \
    useradd --uid 10001 --create-home app && \
    mkdir /data && chown app:app /data
COPY ${SITE_DIR} /site
USER app
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["website-mcp"]
CMD ["serve", "--site", "/site/site.py", "--host", "0.0.0.0", "--port", "8765"]
