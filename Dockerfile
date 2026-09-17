FROM python:3.12-slim-bookworm
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
USER app
ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["jev-mcp"]
CMD ["serve", "--site", "outlook"]
