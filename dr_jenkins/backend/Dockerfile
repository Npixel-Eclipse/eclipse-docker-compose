FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies for Prisma
RUN apk add --no-cache openssl libc6-compat

# Install pnpm
RUN npm install -g pnpm

# Copy package files
COPY package.json pnpm-lock.yaml* ./
COPY prisma ./prisma/

# Install dependencies
RUN if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; else pnpm install; fi

# Copy source
COPY . .

# Generate Prisma client
RUN pnpm prisma generate

# Build application
RUN pnpm build

# Production stage
FROM node:20-alpine AS runner

WORKDIR /app

# Install dependencies for Prisma
RUN apk add --no-cache openssl libc6-compat

# Install pnpm
RUN npm install -g pnpm

# Copy package files and prisma schema
COPY package.json pnpm-lock.yaml* ./
COPY --from=builder /app/prisma ./prisma

# Install production dependencies AND prisma as dev dependency
RUN if [ -f pnpm-lock.yaml ]; then \
      pnpm install --prod --frozen-lockfile && \
      pnpm add -D prisma && \
      pnpm prisma generate; \
    else \
      pnpm install --prod && \
      pnpm add -D prisma && \
      pnpm prisma generate; \
    fi

# Copy built application
COPY --from=builder /app/dist ./dist

# Copy config files
COPY --from=builder /app/config ./config

# Expose port
EXPOSE 4000

# Start command with db push (creates tables if not exist)
CMD ["sh", "-c", "pnpm prisma db push --accept-data-loss && node dist/main"]
