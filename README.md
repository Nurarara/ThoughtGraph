# ThoughtGraph

> See what your thinking is becoming.

ThoughtGraph is a private, spatial thinking environment. Instead of storing ideas in a long list, it places them in a living map where related thoughts move together, themes become visible, and reflection is tied back to real evidence.

The project currently runs as a local-first prototype: your data is stored on your machine by default, no external AI provider is required, and the core experience works without Kafka, Neo4j, Redis, or a cloud account.

## The idea in plain English

Most note-taking tools remember *what* you wrote. ThoughtGraph is exploring whether software can also help you see:

- which ideas keep returning;
- which topics are beginning to connect;
- where your attention is changing over time;
- what sources are shaping your saved material; and
- how your thinking overlaps with people you choose to connect with.

It does this visually. Thoughts, links, images, and videos become nodes. Meaningful relationships become edges. Groups of related nodes become clusters that can be explored by panning, zooming, and focusing.

ThoughtGraph is not mind-reading software, a personality test, or a medical or psychological assessment. Its reflective features describe patterns in the material you saved and show the evidence behind those descriptions.

## What you can do today

The current product supports:

- a cinematic public landing experience at `/`;
- a graph-first workspace at `/app`;
- passwordless magic-link sign-in;
- private, friends-only, and public visibility;
- thoughts, links, images, and videos as first-class graph nodes;
- automatic local embeddings, semantic connections, clusters, and graph layout;
- search that brings matching nodes back into spatial context;
- replies, quotations, follows, friendships, restrictions, and social neighbourhoods;
- explainable discovery of related ideas and adjacent people;
- evidence-backed attention-drift and source-shaping reflections;
- feedback, correction, annotation, and dismissal for reflective insights;
- media upload, processing, thumbnails, playback, size limits, and safe storage paths;
- provenance, trust, moderation, replay, and operational inspection surfaces for prototype evaluation; and
- an explicit migration tool for importing older V1 thoughts into the graph-native model.

### A typical journey

1. Capture a thought privately.
2. ThoughtGraph places it in the semantic field.
3. Related ideas and themes move into view.
4. Open a node to read its full content, thread, quotation, and connections.
5. Explore nearby public or friends-only material when you choose to.
6. Run a reflection and inspect the exact nodes and measurements behind it.

## Honest scope

ThoughtGraph is an ambitious product prototype, not a finished public network.

| Area | Current state |
| --- | --- |
| Personal graph | Working end to end |
| Search and spatial navigation | Working end to end |
| Social relationships and discovery | Working prototype |
| Evidence-backed reflection | Working for attention drift and source shaping |
| Image and video uploads | Working locally |
| Media safety | Uploaded media remains `unreviewed` until explicitly approved and is excluded from discovery |
| Trust, provenance, moderation, and ops | Inspectable prototype boundaries |
| Production deployment | Not ready without the hardening work described below |

Some older feed-style modules still exist in the repository for migration history. The active product is the graph-native application mounted through [`backend/app/api/router.py`](backend/app/api/router.py) and [`frontend/src/components/GraphShell.tsx`](frontend/src/components/GraphShell.tsx).

The active product does **not** currently promise WebSocket updates, account export, account deletion, snapshots, or weekly reports. Those appeared in earlier prototypes but are not mounted in the current API.

## How it works

```text
You capture something
        |
        v
Canonical content node + ownership + visibility
        |
        +--> local text embedding
        +--> semantic edges
        +--> clusters and spatial coordinates
        +--> search and discovery projections
        +--> evidence-backed reflections
```

The important architectural rule is that authored content remains canonical. Search indexes, graph read models, clusters, and reflective outputs are derived views that can be rebuilt.

### Current architecture

- **Frontend:** React, TypeScript, Vite, Canvas, IBM Plex, and Phosphor icons.
- **Backend:** FastAPI, SQLAlchemy, Pydantic, NumPy, and scikit-learn.
- **Default database:** SQLite.
- **Default media storage:** local filesystem.
- **Embeddings:** deterministic 256-dimensional local vectors.
- **Jobs and events:** persisted boundaries that run in-process by default.
- **Read models:** local, rebuildable search and graph projections.

This is a modular monolith on purpose. It keeps the product easy to run while preserving boundaries that can be moved to dedicated infrastructure later.

## Run it locally on Windows

### Requirements

- Python 3.11 or newer;
- Node.js 20.19 or newer, or Node.js 22.12 or newer; and
- npm.

### 1. Start the backend

Open PowerShell in the project folder:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Leave that terminal open.

### 2. Start the frontend

Open a second PowerShell window in the project folder:

```powershell
cd frontend
npm install
npm run dev
```

### 3. Open ThoughtGraph

Visit [http://127.0.0.1:5174](http://127.0.0.1:5174).

In development mode, enter an email address and use the secure sign-in link shown by the application. A real email provider is optional locally.

The API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### If the page says “Failed to fetch”

Check these in order:

1. Open [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health). If it does not load, restart the backend.
2. Confirm the frontend is running on port `5174`.
3. Confirm [`frontend/.env.example`](frontend/.env.example) points to the same backend origin.
4. Restart the frontend after changing an environment variable.

## Privacy and safety

- New nodes are private by default.
- Replies and quotations inherit the target's visibility by default.
- Every authenticated request is resolved to one owner.
- Search, graph, detail, and discovery results are visibility-filtered.
- Session tokens are stored as hashes on the backend.
- Upload byte limits are checked before and during streaming.
- Storage keys are confined to the configured media directory.
- Reflective insights include limitations and evidence references.
- Feedback events never include private annotation or evidence text.

### Important development warning

The default configuration is designed for local development. Do not expose it directly to the public internet.

Before any real deployment, at minimum:

- set `THOUGHTGRAPH_AUTH_MODE=production`;
- set `THOUGHTGRAPH_ALLOW_DEV_AUTH_BYPASS=false`;
- keep `THOUGHTGRAPH_ALLOW_DEV_USER_HEADER_IMPERSONATION=false`;
- configure SMTP for magic-link delivery;
- restrict CORS to the real frontend domain;
- use a managed database and verified migrations;
- use managed object storage and backups;
- add rate limiting and abuse protection; and
- connect a real moderation provider or human review queue.

## How the project can scale

Scaling should follow real product demand rather than adding infrastructure for appearance.

### Stage 1: private alpha

Keep the modular monolith, then add:

- PostgreSQL with a production database driver;
- versioned Alembic migrations;
- managed object storage for media;
- production email delivery and hardened authentication;
- database and media backups;
- a real moderation/review workflow;
- CI, error reporting, metrics, and structured logs; and
- browser end-to-end tests for the core journey.

### Stage 2: growing community

When inline work becomes slow or traffic becomes uneven:

- move embedding, media, graph projection, and reflection jobs to background workers;
- introduce a durable queue and retry policies;
- add Redis only for measured caching or coordination needs;
- place media behind a CDN;
- add rate limiting, quotas, and stronger anti-abuse controls;
- scale search into OpenSearch when the local read model is no longer sufficient; and
- partition heavy graph projection work by user or neighbourhood.

### Stage 3: large network

Only when scale justifies the operational cost:

- move internal event contracts to Kafka or another durable event transport;
- use Temporal or an equivalent system for long-running workflows;
- evaluate Neo4j for traversal-heavy queries that PostgreSQL cannot serve efficiently;
- separate high-traffic services behind stable contracts;
- add tenant isolation, regional data policies, and disaster recovery; and
- introduce calibrated model providers only where they outperform the explainable local baseline.

Kafka, Temporal, OpenSearch, and Neo4j are **future boundaries**, not services secretly running in this repository today.

## Project structure

```text
ThoughtGraph/
|-- backend/
|   |-- app/api/          active HTTP routes
|   |-- app/models/       canonical and derived data models
|   |-- app/services/     graph, media, discovery, trust, and reflection logic
|   |-- app/cli/          migration commands
|   `-- app/tests/        backend regression suite
|-- frontend/
|   |-- src/components/   landing, graph workspace, and product surfaces
|   |-- src/lib/          typed API client and shared decisions
|   `-- public/           web app assets
|-- docs/                 engineering contracts and prototype boundaries
`-- design-qa.md          latest visual verification report
```

Useful starting points:

- [`frontend/src/App.tsx`](frontend/src/App.tsx) — landing/workspace routing;
- [`frontend/src/components/GraphShell.tsx`](frontend/src/components/GraphShell.tsx) — active product shell;
- [`frontend/src/components/GraphCanvas.tsx`](frontend/src/components/GraphCanvas.tsx) — spatial interaction and rendering;
- [`frontend/src/lib/apiClient.ts`](frontend/src/lib/apiClient.ts) — typed frontend/backend contract;
- [`backend/app/api/router.py`](backend/app/api/router.py) — mounted API surface;
- [`backend/app/services/node_service.py`](backend/app/services/node_service.py) — canonical node creation and reads;
- [`backend/app/services/graph_service.py`](backend/app/services/graph_service.py) — graph projection and reconciliation;
- [`backend/app/services/reflective_insight_service.py`](backend/app/services/reflective_insight_service.py) — evidence-backed reflections; and
- [`docs/phase_6_12_verification.md`](docs/phase_6_12_verification.md) — explicit prototype boundaries.

## Verification

Run the backend suite:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Run the frontend tests and production build:

```powershell
cd frontend
npm test
npm run build
npm audit --omit=dev
```

Latest verified baseline:

- 61 backend tests passed;
- 19 frontend tests passed;
- production frontend build passed;
- production dependency audit reported 0 vulnerabilities; and
- the Edge browser journey passed with no console, page, or HTTP errors.

## Importing thoughts from the older prototype

The migration command is explicit, idempotent, and creates a verified SQLite backup before applying changes.

Preview an import without changing the database:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.cli.migrate_legacy_thoughts `
  --database .\thoughtgraph.db `
  --dry-run `
  --visibility private `
  --reconcile-projection
```

Replace `--dry-run` with `--apply` only after reviewing the report.

## Project status

ThoughtGraph has moved beyond a throwaway demo: the graph-native model, privacy rules, upload boundaries, reflective contracts, migration path, and visual product shell are all tested. The next milestone is not “more features.” It is turning the verified local foundation into a safe private alpha with production migrations, real moderation, observability, and browser automation.

That is the scope: make thinking visible without pretending that software knows more about a person than the evidence supports.
