# Production image for Mission Control (Next.js standalone). NEXT_PUBLIC_* are baked at BUILD
# time, so the public auditor URL must be passed as a build arg (see deploy/docker-compose.prod.yml).
FROM node:22-alpine AS deps
WORKDIR /app
RUN npm install -g pnpm@11
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

FROM node:22-alpine AS builder
WORKDIR /app
RUN npm install -g pnpm@11
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Same-origin default: the reverse proxy serves the auditor under /api on the app domain.
ARG NEXT_PUBLIC_AUDITOR_URL=/api
ARG NEXT_PUBLIC_USE_MOCK=false
ENV NEXT_PUBLIC_AUDITOR_URL=$NEXT_PUBLIC_AUDITOR_URL \
    NEXT_PUBLIC_USE_MOCK=$NEXT_PUBLIC_USE_MOCK \
    NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
RUN addgroup -S nodejs && adduser -S nextjs -G nodejs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
