FROM node:20.11.1-alpine3.19 AS base

WORKDIR /app

COPY package.json package-lock.json* bun.lock* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM base AS dev

COPY . /app

CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3000"]

FROM base AS builder

COPY . /app

RUN npm run build

FROM node:20.11.1-alpine3.19 AS runtime

ENV NODE_ENV=production

WORKDIR /app

RUN addgroup -S app && adduser -S app -G app

COPY --from=builder /app/public /app/public
COPY --from=builder /app/.next /app/.next
COPY --from=builder /app/node_modules /app/node_modules
COPY --from=builder /app/package.json /app/package.json

USER app

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
