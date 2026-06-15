# frontend

**Language:** Node.js 20 / Next.js 14 | **Type:** Frontend | **Port:** 3000
**Owner:** frontend-team | **Spec:** `services.yaml`

Customer-facing UI and HITL operator approval interface. Calls the API Gateway at
`NEXT_PUBLIC_API_BASE_URL`.

## Quick start

```bash
# First time only — generate lock file:
cd frontend/web && pnpm install

# From the monorepo root:
make run-frontend APP=web      # Next.js dev server on :3000
make test-unit-frontend APP=web
make lint-frontend APP=web
```

## Environment variables

| Variable                   | Default                 | Description           |
| -------------------------- | ----------------------- | --------------------- |
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | API Gateway base URL  |
| `NEXT_PUBLIC_APP_ENV`      | `development`           | App environment label |

## Key pages

| Route       | Description                                |
| ----------- | ------------------------------------------ |
| `/`         | Home — navigation hub                      |
| `/hitl`     | HITL approval queue — operator approval UI |
| `/requests` | Request status tracking                    |

## API client

`src/lib/api/` contains typed wrappers over the API Gateway REST endpoints defined
in `docs/api/openapi/v1/openapi.yaml`. Regenerate after spec changes:

```bash
make gen-api-client-ts APP=web
```
