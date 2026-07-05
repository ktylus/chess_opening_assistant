FROM node:20-slim

WORKDIR /app

# Dependencies first, so this layer is cached until the lockfile changes.
COPY package.json package-lock.json ./
RUN npm ci

# App code. In dev this is shadowed by a bind mount; it is kept here so the
# image is still runnable on its own.
COPY . .

EXPOSE 5173

# --host makes Vite listen on 0.0.0.0 so it is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
