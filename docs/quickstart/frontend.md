# Quickstart — Frontend (React / Next.js)

> **Stack:** Node 20 · Next.js 14 · TypeScript · React Query · Tailwind CSS · OpenTelemetry Browser SDK
> **Service types:** Customer-facing UI, internal operator dashboard, HITL approval interface
> **Read first:** [docs/quickstart/README.md](README.md) for shared governance rules.

---

## Prerequisites

| Tool             | Version | Install                                                       |
| ---------------- | ------- | ------------------------------------------------------------- |
| Node.js          | 20+     | `brew install node@20` or [nodejs.org](https://nodejs.org/)   |
| pnpm             | 9+      | `npm install -g pnpm`                                         |
| Docker & Compose | 24+     | [docker.com](https://www.docker.com/products/docker-desktop/) |
| make             | any     | pre-installed on macOS/Linux                                  |

---

## Which files are yours

```
frontend/<your-app>/
├── src/
│   ├── app/              ← Next.js App Router pages and layouts
│   ├── components/       ← reusable React components
│   ├── features/         ← domain-specific feature modules
│   ├── lib/
│   │   ├── api/          ← generated API client (from OpenAPI spec)
│   │   └── otel.ts       ← OTel browser instrumentation init
│   └── types/            ← shared TypeScript types (generated from OpenAPI)
├── public/
├── next.config.ts
└── package.json
```

**Files you do NOT own (shared contracts — read-only):**

```
docs/api/openapi/v1/openapi.yaml   ← REST contract — generate TS client from this
docs/api/asyncapi/                 ← Kafka events (backend only; frontend uses REST)
```

---

## Setup

```bash
# 1. Start shared backend infrastructure
docker compose up -d

# 2. Install Node dependencies
pnpm install

# 3. Generate TypeScript API client from OpenAPI spec
make gen-api-client-ts

# 4. Copy and configure environment
cp frontend/<your-app>/.env.example frontend/<your-app>/.env.local
# Required fields:
#   NEXT_PUBLIC_API_BASE_URL   http://localhost:8000
#   NEXT_PUBLIC_OTEL_ENDPOINT  http://localhost:4318

# 5. Start dev server
make run-frontend APP=<your-app>
```

Expected: dev server running at `http://localhost:3000`.

---

## Daily workflow

```bash
make test-frontend APP=<app>       # Jest unit + Playwright e2e tests
make test-unit-frontend APP=<app>  # Jest only (fast, no browser)
make lint-frontend APP=<app>       # ESLint + TypeScript type check
make format-frontend APP=<app>     # Prettier
make run-frontend APP=<app>        # Next.js dev server (hot-reload)
make build-frontend APP=<app>      # production build
```

---

## Key architectural patterns

### API client — always use generated types

Never write raw `fetch()` calls against the REST API. Use the generated client:

```typescript
// Generated from docs/api/openapi/v1/openapi.yaml
import { RequestsApi, Configuration } from "@/lib/api";

const api = new RequestsApi(
  new Configuration({ basePath: process.env.NEXT_PUBLIC_API_BASE_URL }),
);

// Fully typed — no manual interface definitions
const request = await api.createRequest({
  createRequestBody: { prompt, context },
});
```

Regenerate after any OpenAPI spec change: `make gen-api-client-ts`.

### Data fetching — React Query

```typescript
import { useQuery, useMutation } from "@tanstack/react-query";

// Query with automatic refetch for HITL polling
export function useHitlRequest(requestId: string) {
  return useQuery({
    queryKey: ["hitl", requestId],
    queryFn: () => hitlApi.getHitlRequest({ requestId }),
    refetchInterval: (data) => (data?.status === "PENDING" ? 3000 : false),
  });
}
```

### PII — never display raw personal data

```typescript
// Mask PII fields before rendering — apply the same L1-L4 rules as backend
import { maskEmail, maskDocument } from "@/lib/pii";

// In your component:
<span>{maskEmail(user.email)}</span>  // shows j***@example.com
```

Never log PII to the browser console or send it to analytics tools.

### HITL approval interface

The HITL approval UI polls the REST API and records human decisions:

```typescript
// POST /v1/hitl/decisions — record approve or reject
const { mutate: decide } = useMutation({
  mutationFn: (decision: "APPROVED" | "REJECTED") =>
    hitlApi.recordDecision({
      requestId,
      hitlDecisionBody: { decision, reviewer_id: currentUser.id },
    }),
  onSuccess: () => queryClient.invalidateQueries(["hitl"]),
});
```

Full spec: `docs/api/openapi/v1/openapi.yaml` — `/v1/hitl` paths.

### Structured logging / OTel

```typescript
// src/lib/otel.ts — initialized in layout.tsx
import { WebTracerProvider } from "@opentelemetry/sdk-trace-web";

// In components — use the global tracer, not console.log
import { trace } from "@opentelemetry/api";

const tracer = trace.getTracer("frontend");

function MyComponent() {
  const span = tracer.startSpan("user-action");
  // ... do work
  span.end();
}
```

Never use `console.log()` in production code paths.

---

## Observability

The Next.js app exports Web Vitals as OTel metrics automatically. Add custom spans for critical user interactions:

```typescript
// Track CUJ-001 milestones
const span = tracer.startSpan("request-submission");
span.setAttribute("request.type", requestType);
span.setAttribute("user.role", userRole);
// ... submit
span.setStatus({ code: SpanStatusCode.OK });
span.end();
```

---

## Testing conventions

```typescript
// Unit test — Jest + React Testing Library
describe("HitlApprovalCard", () => {
  it("shows approve button only for pending requests", () => {
    render(<HitlApprovalCard status="PENDING" />);
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
  });
});

// E2E test — Playwright
test("user can submit a request and see HITL approval", async ({ page }) => {
  await page.goto("/requests/new");
  await page.fill('[name="prompt"]', "Test prompt");
  await page.click('button[type="submit"]');
  await expect(page.locator('[data-testid="hitl-status"]')).toHaveText("PENDING");
});
```

Coverage must be ≥ 80% for unit tests. E2E tests cover all CUJ-001 steps.

---

## Deployment

```bash
# Build production image
make build-frontend APP=<your-app>

# Deploy to staging
make deploy-staging SERVICE=<your-app>

# Verify
curl http://staging.internal/<your-app>/api/health
```

---

## Key ADRs for frontend developers

| ADR                                                       | Why it matters to you                               |
| --------------------------------------------------------- | --------------------------------------------------- |
| [ADR-0002](../adr/ADR-0002-technology-stack-selection.md) | Next.js / React rationale                           |
| [ADR-0003](../adr/ADR-0003-async-api-strategy.md)         | REST vs Kafka — frontend only uses REST             |
| [ADR-0011](../adr/ADR-0011-hitl-hotl-model.md)            | HITL approval UI — what the operator must see       |
| [ADR-0012](../adr/ADR-0012-pii-masking-strategy.md)       | PII masking in the UI before display or analytics   |
| [ADR-0015](../adr/ADR-0015-feature-flag-strategy.md)      | Feature flags — use OpenFeature JS SDK for UI flags |
