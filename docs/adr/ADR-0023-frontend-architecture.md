# ADR-0023 — Frontend Architecture

**Status:** Accepted
**Date:** 2026-05-28
**Authors:** Tech Lead, Frontend Lead
**Spec:** N/A — architectural decision record for the frontend scaffold
**Supersedes:** None | **Superseded by:** None

---

## Context

The monorepo ships a Next.js frontend (`frontend/frontend/`) that serves the HITL operator
approval UI. When this frontend was scaffolded, several architectural choices were made
implicitly without a recorded decision:

1. **Framework selection** — Next.js 14 with App Router was chosen, but the rationale was not
   documented. Teams adopting this template need to understand the tradeoffs before extending it.
2. **Rendering strategy** — the HITL operator UI has different rendering requirements than a
   typical public-facing application (authenticated, low-traffic, near-real-time updates).
3. **API communication** — the frontend calls the api-gateway REST API. The contract between
   frontend and api-gateway is not formally defined (addressed in Wave 6 via Pact).
4. **Test strategy** — Jest + Testing Library for unit/component tests; Playwright for E2E.
   The split between these two layers was not documented.
5. **Authentication** — not yet implemented in the scaffold; this ADR establishes the intended
   approach so the community knows the design before extending.

---

## Decision

### 1. Framework: Next.js 14, App Router

Next.js 14 with the App Router is the chosen framework.

**Why Next.js over alternatives:**

| Option           | Reason not chosen                                                        |
| ---------------- | ------------------------------------------------------------------------ |
| Create React App | No SSR, no file-based routing, maintenance abandoned by Meta             |
| Vite + React     | Good DX but no SSR out of the box; adds complexity for server components |
| Remix            | Strong data patterns but smaller ecosystem; harder to onboard            |
| Next.js          | SSR + static generation + App Router; large ecosystem; TypeScript-first  |

**Why App Router over Pages Router:**

- Server Components reduce client-side JavaScript for the operator dashboard.
- React Server Actions simplify form submissions (HITL approve/reject) without a client-side
  fetch layer.
- `next/navigation` hooks provide type-safe routing.
- Pages Router is in maintenance mode; new Next.js features target App Router only.

### 2. Rendering Strategy

The HITL operator UI has two primary views:

| View                | Rendering strategy              | Rationale                                                          |
| ------------------- | ------------------------------- | ------------------------------------------------------------------ |
| Login / Landing     | Static (`generateStaticParams`) | No personalisation; cacheable                                      |
| HITL Pending Queue  | Server Component + polling      | List must be fresh; polling interval 5 s acceptable for ops UI     |
| HITL Decision Form  | Client Component                | Requires user interaction; approve/reject submit via Server Action |
| Audit Log / History | Server Component + ISR          | Read-only; 30-second stale-while-revalidate acceptable             |

**Real-time updates:** The HITL queue polls the `/v1/hitl` endpoint at 5-second intervals.
WebSocket support is deferred — the operator UI is low-traffic (ops-internal) and polling
at 5 s provides acceptable UX without added infrastructure complexity.

### 3. API Communication

The frontend communicates with the api-gateway REST API (`/v1/` prefix).

- **Base URL** is injected via `NEXT_PUBLIC_API_BASE_URL` environment variable (set via Helm
  ConfigMap in production; `.env.local` in development).
- API client code lives in `frontend/src/lib/api/` and is generated from the OpenAPI spec
  (`make gen-api-client-ts`) to ensure type safety and catch contract drift.
- Authentication headers (Bearer token) are added in the API client layer, not in individual
  components.

**Consumer-driven contract testing (Pact):** introduced in Wave 6. Until then, type safety
from the generated OpenAPI client is the primary protection against contract drift.

### 4. Authentication

Authentication is **not implemented** in the Wave 4 scaffold. The intended approach:

- **Provider:** an external IdP (Keycloak, Auth0, or Azure AD — project-specific choice).
- **Protocol:** OIDC with PKCE. The frontend receives a JWT; every api-gateway call includes
  `Authorization: Bearer <jwt>`.
- **Implementation path:** `next-auth` (Auth.js) for the Next.js session layer. The operator
  role (`hitl:operator`) is checked by the api-gateway via the JWT `roles` claim.
- **HITL operator role** is defined in `specs/security/rbac-model.md` (Wave 8).

Teams adopting this template must implement authentication before any production deployment.
The `PRR-TEMPLATE.md` includes an auth gate (`auth_implemented`) that blocks PRR sign-off.

### 5. Test Strategy

| Layer       | Tooling                              | Scope                                                              |
| ----------- | ------------------------------------ | ------------------------------------------------------------------ |
| Unit        | Jest + React Testing Library         | Individual components, hooks, API client functions                 |
| Integration | N/A (api-gateway handles this layer) | N/A                                                                |
| Contract    | Pact (Wave 6)                        | REST contract between frontend (consumer) and api-gateway          |
| E2E         | Playwright                           | Full user journeys: submit request → HITL pending → approve/reject |

**Coverage target:** ≥ 80% for `src/` (excluding generated API client code). Configured in
`jest.config.ts` with `collectCoverageFrom` pointing to `src/**/*.{ts,tsx}`.

**Why Jest + React Testing Library for components:**

React Testing Library's philosophy (test behaviour, not implementation) aligns with this
codebase's convention of testing outcomes rather than internals. Enzyme is not used.

**Why Playwright for E2E:**

Playwright supports Chromium, Firefox, and WebKit. Its async API and robust element locators
make HITL approval flows (which involve polling and state transitions) easier to test reliably
than with Cypress. It is already in `devDependencies`.

### 6. Styling and Component Library

No component library is pre-installed in the scaffold. Project teams choose their own
(Tailwind CSS, shadcn/ui, MUI, or plain CSS Modules are all compatible with Next.js 14).

The scaffold ships with ESLint (`next/core-web-vitals`) and Prettier for consistent formatting.

### 7. TypeScript Configuration

Strict TypeScript is enforced (`"strict": true` in `tsconfig.json`). The API client generated
from the OpenAPI spec is fully typed. Components must not use `any` — use `unknown` and
narrow at boundaries.

---

## Consequences

### Positive

- App Router + Server Components reduces JavaScript sent to operators; improves initial load.
- Generated TypeScript API client catches contract drift at compile time.
- Playwright E2E tests can exercise the full HITL approval flow including polling.
- Clear rendering strategy per view type simplifies future development decisions.

### Negative / Trade-offs

- App Router has a steeper learning curve than Pages Router for developers new to Next.js 14.
  Mitigation: `docs/quickstart/frontend.md` provides an onboarding guide.
- Server Actions introduce a server-side execution context within the frontend — this must be
  treated as an API boundary for the purposes of input validation and authentication.
- Polling at 5 s is simple but not optimal under high operator concurrency. If > 20 simultaneous
  operators are expected, migrate to WebSocket or Server-Sent Events.
- Authentication is deferred — teams must implement it before any production deployment (blocked
  by PRR checklist).

---

## Alternatives Considered

**Single-page application (Vite + React, no SSR):**
Considered for simplicity. Rejected because the HITL audit log view benefits from SSR for
performance and SEO (internal tooling portals are increasingly indexed for internal search).

**Pages Router (Next.js 12/13 style):**
Considered for familiarity. Rejected because App Router is the strategic direction for Next.js
and new features (Server Actions, Partial Prerendering) only target App Router.

**WebSocket for real-time HITL updates:**
Considered for lower latency. Deferred: adds infrastructure complexity (sticky sessions or a
pub-sub layer) that is not justified for an internal ops UI with low operator concurrency.
