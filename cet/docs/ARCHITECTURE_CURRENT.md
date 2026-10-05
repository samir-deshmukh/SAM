# CETFind — Current System Architecture

> Current production architecture as deployed in October 2026. Older planning documents in this repository describe an earlier Streamlit-based design and are retained as historical records.

## 1. High-level flow

Browser
→ Render Static Site (CETFind frontend)
→ HTTPS requests to FastAPI backend
→ PostgreSQL

Admin browser
→ FastAPI /admin
→ PostgreSQL + private import/derived-data pipeline

CAP source PDFs
→ admin import/review/approval
→ normalized PostgreSQL tables
→ derived runtime data
→ candidate API

## 2. Runtime components

### Frontend
- Static HTML/CSS/JavaScript in `site/`.
- Hosted separately from the API.
- Candidate search calls `/api/options`, `/api/search`, and college-detail endpoints.
- The browser does not receive the master cutoff dataset.

### Backend
- FastAPI application in `backend/`.
- Uvicorn/ASGI runtime.
- Public API and admin application are served by the same backend service.
- FastAPI OpenAPI, Swagger UI and ReDoc are disabled in production.
- `/healthz` is a lightweight liveness endpoint.

### Database
- PostgreSQL is the source of truth for production data.
- Public search uses SQL aggregation and pagination.
- The public search path sends only the requested result page to pandas.
- Database indexes support cutoff filtering, program/institution lookup and derived runtime data.

## 3. Public search request

1. User selects course, percentile, optional city and sort order.
2. Frontend sends a bounded request to `/api/search`.
3. Backend validates parameters and applies the public API rate limit.
4. PostgreSQL joins `cutoffs`, `institutes`, and `programs`.
5. SQL aggregates one summary row per institution.
6. SQL applies sorting and pagination.
7. A total count is returned with the page.
8. Backend converts the bounded result page into the API response.
9. Browser renders college cards.

This avoids the previous design where the complete matching cutoff set was loaded into pandas for every public search.

## 4. College details

A college card can request institution-specific trend/detail data. Queries are scoped by institution and course rather than loading the whole dataset into the browser.

Seat-matrix availability is derived from the runtime seat-matrix data. The current design keeps the master data server-side.

## 5. Import and publishing pipeline

1. Administrator uploads a CAP source PDF.
2. Preflight validates the file.
3. Extraction/normalization converts source material into structured records.
4. Import is staged for review.
5. Administrator explicitly approves the import.
6. Publishing promotes the approved release.
7. Derived public runtime data can be rebuilt after approved data changes.

A restart does not implicitly approve staged imports.

## 6. Security boundaries

- Database credentials remain server-side.
- Master datasets are not mounted as public static files.
- Production API documentation endpoints are disabled.
- CORS is restricted to the canonical frontend origin.
- Admin sessions use secure cookie settings in production.
- Admin state-changing operations use CSRF protection.
- Authentication checks account status and session authentication version.
- Login attempts are throttled.
- Public feedback has a separate limiter.
- Public analytics stores anonymous event/session identifiers rather than IP addresses.
- Security headers include CSP, frame protection, MIME sniffing protection, referrer policy and permissions policy.
- Import processing is serialized because PDF processing is memory-heavy on the free instance.
- The public API rate limiter is intentionally part of production protection and must not be bypassed during capacity testing.

## 7. Scalability model

Current free deployment is a single public backend service backed by PostgreSQL. It is not evidence of a multi-instance load-balanced architecture.

For higher traffic, the logical evolution is:

CDN/static frontend
→ load balancer/reverse proxy
→ multiple FastAPI instances
→ PostgreSQL
→ optional cache/queue for workloads that justify them

Horizontal scaling requires shared state for anything currently stored in process memory, especially rate limiting and other per-process caches. Database connection limits must also be sized before increasing backend instances.

## 8. Capacity testing

Production tests must distinguish:
- protected public capacity (including the production rate limiter);
- backend/application capacity;
- database capacity.

A single client IP cannot honestly simulate hundreds of independent users against a per-IP limiter without changing the test topology. Therefore a burst that produces 429 responses is a protection-limit result, not a server-capacity result.

## 9. Important source-of-truth rule

The current implementation should be used when describing the system. `docs/ARCHITECTURE.md`, `docs/PRD.md`, `docs/DECISIONS.md`, and some comments contain historical Streamlit-era decisions and should not be presented as the current deployed architecture.
