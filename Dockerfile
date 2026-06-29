ARG ALPINE_VERSION=3.22
FROM python:3.12-alpine${ALPINE_VERSION}

ARG POSTGRES_CLIENT_PKG=postgresql16-client
ARG MYSQL_CLIENT_PKG=mariadb-client

# Install deps: restic, PostgreSQL/MySQL client tools, jq, bash, ca-certs
RUN apk add --no-cache \
      restic \
      ${POSTGRES_CLIENT_PKG} \
      ${MYSQL_CLIENT_PKG} \
      bash \
      ca-certificates \
      curl

WORKDIR /opt/restic-backup

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN --mount=from=ghcr.io/astral-sh/uv:0.11.25,source=/uv,target=/bin/uv \
    UV_PROJECT_ENVIRONMENT="/usr/local/" \
    uv sync --locked --no-dev --no-editable --compile-bytecode

ENTRYPOINT ["restic-backup"]
