# Build the static UI, then serve it with nginx and proxy /api to the
# FastAPI backend that runs on the host (it launches the sandbox containers).
FROM node:20-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV API_UPSTREAM=http://host.docker.internal:8000
EXPOSE 80
