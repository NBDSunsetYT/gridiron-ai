# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS dependencies
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json ./
# Optional public CA mount is only for managed authoring-environment builds.
# Railway's normal builder uses its trusted system roots without this mount.
RUN --mount=type=secret,id=proxy_ca if [ -f /run/secrets/proxy_ca ]; then NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca npm ci --strict-ssl=true; else npm ci --strict-ssl=true; fi
FROM dependencies AS build
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build
FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080 HOSTNAME=0.0.0.0 DATA_BACKEND=supabase GRIDIRON_CLOUD_ONLY=1 DATA_DIR=/tmp/gridiron-hosted-cache
RUN groupadd --system --gid 1001 gridiron && useradd --system --uid 1001 --gid 1001 gridiron
COPY --from=build --chown=gridiron:gridiron /app/.next/standalone ./
COPY --from=build --chown=gridiron:gridiron /app/.next/static ./.next/static
COPY --from=build --chown=gridiron:gridiron /app/public ./public
COPY --from=build --chown=gridiron:gridiron /app/migrations ./migrations
COPY --chown=gridiron:gridiron deployment/railway/start-web.mjs ./deployment/start-web.mjs
USER gridiron
EXPOSE 8080
CMD ["node", "deployment/start-web.mjs"]
