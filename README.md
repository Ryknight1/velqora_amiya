# VelQora — AI Pre-Meeting Briefing Agent

Enter a company or person, an optional website/LinkedIn URL, a meeting time and purpose. VelQora researches the
**last 30 days** with Tavily, drafts an analysis through the Bifrost LLM gateway, **checks every factual claim against
the retrieved source text**, and returns a one-page, source-backed briefing.

* **Frontend** – your original HTML/CSS/vanilla-JS design, split into files, visually unchanged.
* **Backend** – FastAPI, Pydantic, SQLite (stdlib), asynchronous job + polling.
* **Research** – Tavily (free tier, credit-conscious: ≤ 6 one-credit searches per briefing).
* **AI** – Bifrost (OpenAI-compatible gateway). The model is configuration only.

> Nothing is faked. If Tavily or Bifrost isn't configured you get a clear error or a clearly-labelled reduced briefing,
> never invented data.

## Architecture

```
Browser (vanilla JS)                         FastAPI backend
 index.html ── api.js ──fetch──► POST /api/research ─► job (SQLite) ─► ResearchService (asyncio task)
   │  polls GET /api/research/{id}                                     │
   │  ◄── stage · progress · message (real)                            ├─ 1 validate input (URL/SSRF checks)
   ▼                                                                   ├─ 2 ResearchAgent ──► TavilyService ──► Tavily API
 cards fill with the real briefing                                     ├─ 3 clean · dedupe · rank sources
 briefing.html = full 10-section briefing                              ├─ 4 date validation (30-day window)
                                                                       ├─ 5 AnalysisAgent ──► BifrostService ──► Bifrost ──► LLM
                                                                       ├─ 6 VerificationAgent (deterministic, no LLM tokens)
                                                                       └─ 7 BriefingAgent ─► validated JSON (Pydantic) ─► SQLite
```

### How trust is handled

| Label | Meaning |
|---|---|
| **verified** | Numbers, names and key words of the claim were found in a retrieved source (source IDs attached). For *recent developments* the source must also have a reliable date inside the 30-day window. |
| **undated / outdated** | Grounded in a source, but that source has no reliable date or is older than 30 days → shown under "Not confirmed as recent", never as a recent development. |
| **unverified** | Could not be matched to any source → excluded from every verified section, listed separately. |
| **analysis** | AI-written talking points, questions, risks, opportunities → always labelled *AI analysis*, never counted as verified. |
| **unavailable** | A gap (no sources, no people found, AI down…) reported as an *open question* instead of being filled in. |

"Verified" is a **grounding check** (the wording is in the source), not proof the source is correct. Tune strictness with
`VERIFY_MIN_OVERLAP`. Dates come from Tavily's `published_date`; a strict `/YYYY/MM/DD/` URL pattern is used as a
fallback (`date_source: "url"`); otherwise the source is `undated`.

## Folder structure

```
velqora/
├── frontend/
│   ├── pages/        index.html (landing + live app) · signin.html · briefing.html (full 10-section briefing)
│   ├── assets/css/   variables · global · animations · components · responsive   (split from the original, unchanged)
│   ├── assets/js/    api.js · auth.js · research.js · briefing.js · app.js
│   └── README.md
├── backend/
│   ├── app/
│   │   ├── main.py  config.py  dependencies.py  security.py  exceptions.py
│   │   ├── api/routes/   health · research · briefing · auth
│   │   ├── agents/       research · analysis · verification · briefing · prompts
│   │   ├── services/     tavily · bifrost · research (jobs) · briefing · http_client
│   │   ├── schemas/      research · briefing · auth   (Pydantic)
│   │   ├── utils/        date_utils · source_utils · validation
│   │   └── database/     connection · models (SQLite repositories)
│   ├── tests/            test_health · test_research · test_briefing (+ helpers)
│   ├── requirements.txt  .env.example
├── .gitignore  README.md
```

Differences from the proposed tree: `dashboard.html` and `research.html` were **not** created (the product is one
landing-page workflow; empty pages would have been dead weight). Added `briefing.html` (needed for the full briefing),
`prompts.py`, `security.py`, `exceptions.py`, `http_client.py` (swappable HTTP layer).

## Prerequisites

* Python 3.10+ (3.12 recommended)
* A free Tavily API key – <https://app.tavily.com>
* Node.js **or** Docker to run Bifrost, plus **one LLM provider key** with a free tier (e.g. Groq or Google Gemini –
  check the provider's current free-tier terms; Bifrost itself provides no tokens)

## Install

```bash
cd velqora/backend
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
```

## Configure

### Tavily
Put your key in `backend/.env`:
```
TAVILY_API_KEY=tvly-...
```
The free plan includes a monthly credit allowance (1 credit per basic search). One briefing runs at most
`TAVILY_MAX_SEARCHES_PER_RESEARCH` (default 6) searches; identical searches are cached for 6 h; `TAVILY_DAILY_CALL_CAP`
(default 100) is a hard safety stop; per-IP rate limits apply. `GET /api/health/services` checks the key through
Tavily's `/usage` endpoint, which does not consume search credits.

### Bifrost (LLM gateway)
This project uses **Bifrost by Maxim AI** ([github.com/maximhq/bifrost](https://github.com/maximhq/bifrost),
docs: <https://docs.getbifrost.ai>) – a self-hosted gateway with an OpenAI-compatible API. Not to be confused with
other projects that share the name.

1. Start it (see the official quickstart for the current command; at the time of writing):
   ```bash
   npx -y @maximhq/bifrost          # serves on http://localhost:8080
   # or: docker run -p 8080:8080 maximhq/bifrost
   ```
2. Open <http://localhost:8080>, add a **provider** and its API key (e.g. Groq or Gemini).
3. Find the exact model id: `curl http://localhost:8080/v1/models`. Model ids look like `provider/model-name`.
4. In `backend/.env`:
   ```
   BIFROST_BASE_URL=http://localhost:8080
   BIFROST_MODEL=<provider/model-id from step 3>
   BIFROST_API_KEY=          # only if your Bifrost enforces auth/virtual keys
   ```
   (`BIFROST_AUTH_MODE=virtual_key` sends the key as `x-bf-vk` instead of a Bearer token.)

**Switching or upgrading the model (e.g. when you get the extra 8K-token budget) = change `BIFROST_MODEL`
(and `BIFROST_MAX_TOKENS` if desired) and restart.** No agent, prompt or frontend code is model-specific. One briefing
uses a single LLM call (≈ 2–3K prompt tokens + ≤ `BIFROST_MAX_TOKENS` output, plus one retry only if the reply isn't
valid JSON). Verification uses no tokens.

## Run

```bash
cd velqora/backend
uvicorn app.main:app --reload --port 8000
```
Open **<http://localhost:8000/>** – FastAPI serves the frontend from the same origin (no CORS needed).
Interactive API docs: <http://localhost:8000/api/docs>.

Alternative: serve `frontend/` separately and keep the backend on :8000:
```bash
cd velqora/frontend && python -m http.server 5500     # then open http://localhost:5500/pages/index.html
```
`api.js` talks to `http://localhost:8000` automatically on localhost; override with
`<script>window.VELQORA_API_BASE="https://your-api"</script>` before `api.js`. Add the frontend origin to `CORS_ORIGINS`.

Check everything is wired: `curl localhost:8000/api/health/services` (add `?deep=true` to also run a tiny model call).

## API

| Method & path | Purpose |
|---|---|
| `GET /api/health` | Backend is up |
| `GET /api/health/services[?deep=true]` | FastAPI / Tavily / Bifrost configuration + connectivity (no secrets returned) |
| `POST /api/research` | Validate input, start an async job → `202 {research_id, status, stage, progress…}` |
| `GET /api/research/{id}` | Status (`queued/running/completed/failed`), stage, progress, message, sources, `briefing_id` |
| `POST /api/briefing/generate` | `{research_id, force?}` – generate a briefing from finished research (idempotent; `force` re-runs the model) |
| `GET /api/briefing/{id}` | Status + the validated briefing JSON |
| `POST /api/auth/register` · `/login` · `GET /me` | Optional accounts (scrypt-hashed passwords, JWT) |

```bash
curl -X POST localhost:8000/api/research -H 'Content-Type: application/json' \
  -d '{"name":"Aurelia Systems","url":"aurelia.com","meeting_time":"Fri 14 Nov 11:00","purpose":"Investor meeting"}'
curl localhost:8000/api/research/<research_id>
curl localhost:8000/api/briefing/<briefing_id>
```
Stages reported while polling: `validating → searching → processing → date_validation → analyzing → verifying → preparing → completed`.
Errors always look like `{"error":{"code","message","details?"}}`. Main codes: `422 validation_error`, `401 unauthorized`,
`404 not_found`, `409 research_not_ready`, `429 rate_limited / upstream_quota_exceeded`, `503 tavily_not_configured`,
`502 upstream_error`.

The briefing JSON extends the reference schema: `overview`, `key_people`, `recent_developments`, `important_news`,
`business_insights`, `industry_information`, `industry_tags`, `meeting_talking_points`, `suggested_questions`,
`potential_risks`, `opportunities`, `open_questions`, `undated_information`, `unverified_claims`, `sources[]`
(`source_id, title, url, publisher, published_date, date_status, retrieved_at, supports_claims, verification_status…`),
`verification_summary`, `ai`, `warnings`. Models live in `backend/app/schemas/briefing_schema.py`.

## Security notes

* All keys stay in `backend/.env` (git-ignored); never sent to the browser; log lines are scrubbed of key-like strings.
* The backend never fetches user-supplied URLs (no SSRF surface); URLs are validated anyway (http/https only, no
  private/loopback/internal hosts, no credentials/odd ports).
* Web text is untrusted: HTML stripped, instruction-like sentences removed, wrapped in delimited blocks, the model is
  told to treat it as data, and its output is only accepted after source verification. The frontend escapes every
  dynamic value before rendering.
* Per-IP rate limits, request timeouts, retries with backoff, safe error messages, CSP and security headers on pages.
* Prototype caveats: JWT is kept in `localStorage` (use httpOnly cookies for production); the rate limiter and job
  runner are in-process (use Redis + a worker queue if you scale out); SQLite is single-node.

## Tests

```bash
cd backend && pytest -q
```
No network or keys needed – Tavily and Bifrost are replaced by fake transports. Covers validation/SSRF, date
filtering, source dedupe/ranking, Tavily retries/cache/caps, Bifrost request shape, JSON handling, claim
verification, briefing assembly and schema, the full pipeline over HTTP, auth, rate limiting and CORS.
Live checks (need your keys): `GET /api/health/services?deep=true`, then run a real research from the UI.

## Troubleshooting

| Symptom | Fix |
|---|---|
| UI says *backend isn't reachable* | Start uvicorn; if the frontend is on another port add it to `CORS_ORIGINS` |
| `503 tavily_not_configured` | Set `TAVILY_API_KEY`, restart |
| `tavily_auth_failed` / quota messages | Key wrong, or free credits used up (see `/api/health/services`) |
| Brief says *AI analysis unavailable* | Check `/api/health/services`: Bifrost running? provider key added in Bifrost? `BIFROST_MODEL` exact id from `/v1/models`? |
| `bifrost_bad_request` | Model id wrong or provider not configured in Bifrost |
| `llm_invalid_json` | Model too weak for JSON; pick another, or set `BIFROST_JSON_MODE=true` if supported |
| Many claims "unverified" | Sources are short snippets; use `TAVILY_SEARCH_DEPTH=advanced` (2 credits/search) or lower `VERIFY_MIN_OVERLAP` slightly |
| "No dated developments" | Little recent coverage, or sources lack publication dates (they're listed as undated, not hidden) |
| Rate-limit message | Raise `RESEARCH_RATE_LIMIT_PER_HOUR` (each research costs Tavily credits) |
