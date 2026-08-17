# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Development: Vite dev server with HMR
# ---------------------------------------------------------------------------
FROM node:20-alpine AS development

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci

COPY . .

# VITE_* values are baked into the bundle at build time and are PUBLIC.
# Never pass a secret here.
ARG VITE_API_BASE_URL
ARG VITE_PUBLIC_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_PUBLIC_BASE_URL=$VITE_PUBLIC_BASE_URL

RUN npm run build

# ---------------------------------------------------------------------------
# Production: static files behind nginx
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS production

RUN rm -rf /usr/share/nginx/html/* \
    && addgroup -g 10001 -S spa \
    && adduser -u 10001 -S spa -G spa

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
