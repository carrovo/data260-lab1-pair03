# Builds the React app and serves it with nginx on port 9036. nginx also acts
# as the single entry point (gateway) that forwards API calls to the six
# backend services, so the browser only ever talks to one origin.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
# Student requests use this prefix; nginx strips it and routes by path.
# (The SPA has its own /jobs, /events ... pages, so the API cannot share them.)
ARG VITE_API_URL=/gw
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 9036
HEALTHCHECK --interval=10s --timeout=3s --retries=6 \
  CMD wget -qO- http://127.0.0.1:9036/healthz || exit 1
