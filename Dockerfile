FROM node:22-bookworm-slim AS dependencies
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends python3 make g++ && rm -rf /var/lib/apt/lists/*
COPY package.json package-lock.json ./
RUN npm ci

FROM dependencies AS build
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0 DATA_DIR=/data
RUN groupadd --system --gid 1001 gridiron && useradd --system --uid 1001 --gid 1001 gridiron && mkdir -p /data && chown gridiron:gridiron /data
COPY --from=build --chown=gridiron:gridiron /app/.next/standalone ./
COPY --from=build --chown=gridiron:gridiron /app/.next/static ./.next/static
COPY --from=build --chown=gridiron:gridiron /app/public ./public
COPY --from=build --chown=gridiron:gridiron /app/migrations ./migrations
USER gridiron
EXPOSE 3000
VOLUME ["/data"]
CMD ["node", "server.js"]
