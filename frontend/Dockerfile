FROM node:20-alpine AS builder
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent

# VITE_API_BASE_URL is baked into the static bundle at build time.
# Pass it via --build-arg when building for non-local environments.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY frontend/ ./
RUN npx tsc -b tsconfig.app.json && npx vite build

FROM nginx:stable-alpine

COPY --from=builder /app/dist /usr/share/nginx/html

RUN rm /etc/nginx/conf.d/default.conf
COPY frontend/nginx.conf /etc/nginx/conf.d/

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
