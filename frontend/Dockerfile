# --- Dependencies stage: shared by the dev server and the production build ---
FROM node:22-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# --- Dev stage: Vite dev server with hot reload.
# docker-compose.dev.yml bind-mounts ./frontend over /app and keeps this image's node_modules
# in an anonymous volume, so source edits on the host are picked up without a rebuild. ---
FROM deps AS dev

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# --- Build stage: compile the SPA with Vite ---
FROM deps AS build

COPY . .
RUN npm run build

# --- Runtime stage (default target): serve static files and proxy /api with nginx ---
FROM nginx:1.28-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
