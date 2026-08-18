# One image, two services. The web app and the worker run the same code with
# different start commands (see railway.json), so they can never drift.
FROM node:22-slim AS base
WORKDIR /app
# Certificates for outbound HTTPS (CT logs, RDAP registries, site probes).
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci

FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM base AS runtime
ENV NODE_ENV=production
# The worker needs tsx and the full source; the web app needs the Next build.
# Shipping both in one image keeps the two services byte-identical.
COPY --from=deps /app/node_modules ./node_modules
COPY --from=build /app/.next ./.next
COPY . .

EXPOSE 3000
# Overridden per service. Default is the web app.
CMD ["npm", "run", "start"]
