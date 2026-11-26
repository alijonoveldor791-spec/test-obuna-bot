FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /bot
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
RUN useradd --create-home bot && mkdir -p storage/pdf storage/previews && chown -R bot:bot /bot
USER bot
EXPOSE 8080
CMD ["sh", "scripts/start.sh"]
