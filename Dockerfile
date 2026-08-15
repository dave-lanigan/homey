# ---- Frontend (Nuxt static) ----
FROM oven/bun:1 AS ui

WORKDIR /ui

COPY ui/package.json ui/bun.lock ./
RUN bun install --frozen-lockfile

COPY ui/ .

# Public Clerk key is baked into the static build. Leave API base empty for same-origin.
ARG NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
ARG NUXT_PUBLIC_API_BASE=
ENV NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY=$NUXT_PUBLIC_CLERK_PUBLISHABLE_KEY \
    NUXT_PUBLIC_API_BASE=$NUXT_PUBLIC_API_BASE \
    NUXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in \
    NUXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up

RUN bun run generate

# ---- API runtime ----
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    PORT=8080

# Install deps from the lockfile first for better layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY api/ ./api/
COPY --from=ui /ui/.output/public ./ui/.output/public

EXPOSE 8080

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
