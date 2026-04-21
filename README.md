# ThoughtGraph

ThoughtGraph is a local-first thought-mapping product that turns short-form thoughts into a semantic graph, extracts clusters and patterns, and adds a social layer so users can see how their thinking connects to other people.

The core idea is simple: most thinking tools store text, but they do not reveal structure. ThoughtGraph treats each thought as a node, links thoughts by semantic similarity, groups them into evolving clusters, and uses that graph to generate insights, influence signals, snapshots, and weekly summaries.

## Purpose

ThoughtGraph exists to help a user answer three questions:

1. What am I actually thinking about?
2. How is my thinking changing over time?
3. How is my mind being shaped by other people?

V1 answered the first two for a single user. V2 expands the product into a social intelligence layer without breaking the solo experience.

## Product Goal

The product goal is to make mental structure visible.

Instead of presenting a flat feed of notes or posts, ThoughtGraph aims to show:

- recurring topics
- emotional concentration
- semantic tension between ideas
- dominant clusters of thought
- cross-user reply and influence patterns
- shareable states of mind

The intended outcome is not just storage. It is reflection, interpretation, and network context.

## What Is Implemented

This repository currently includes a working V1 foundation plus a broad V2 implementation.

### V1 foundation

- thought creation and storage
- semantic similarity graph generation
- connected-component clustering
- insight generation
- timeline filtering
- WebSocket graph updates
- local demo seed data

### V2 social layer

- user profiles
- follow and unfollow flows
- public and private thought visibility
- cross-user replies
- social graph overlay on the main graph
- notification system
- influence scoring
- social feed
- trending clusters
- suggested users
- graph snapshots
- weekly reports
- onboarding state
- notification preferences
- data export
- account deletion

## Product Principles

The repo is built around a few constraints:

- V2 is additive. V1 behavior remains the default.
- Existing core endpoints stay compatible by default.
- The solo graph experience must still work for a user who never follows anyone.
- Social features are opt-in, not forced.
- The architecture should be easy to swap from local heuristics to external services later.

## Architecture

### Backend

The backend is a FastAPI application in [`backend/app`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/app).

Main responsibilities:

- persist thoughts, users, follows, notifications, reports, and snapshots
- compute graph structure
- compute insights and influence scores
- expose REST and WebSocket APIs
- keep V1 and V2 response contracts stable

Key modules:

- [`backend/app/main.py`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/app/main.py): app bootstrap
- [`backend/app/api/routes`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/app/api/routes): API routes
- [`backend/app/services/graph_pipeline.py`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/app/services/graph_pipeline.py): graph building and social overlay
- [`backend/app/services/insight_engine.py`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/app/services/insight_engine.py): insight generation
- [`backend/app/services/social_service.py`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/app/services/social_service.py): replies, feed, discovery, follows
- [`backend/app/services/influence_service.py`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/app/services/influence_service.py): influence scoring
- [`backend/app/services/snapshot_service.py`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/app/services/snapshot_service.py): snapshot generation
- [`backend/app/services/report_service.py`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/app/services/report_service.py): weekly report generation

### Frontend

The frontend is a React + TypeScript + Vite app in [`frontend/src`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/frontend/src).

Main responsibilities:

- render the main graph experience
- render additive V2 pages and panels
- manage graph, social, notification, snapshot, and report state
- preserve the original V1 layout while adding social capabilities

Key modules:

- [`frontend/src/App.tsx`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/frontend/src/App.tsx): top-level shell and route switching
- [`frontend/src/components/NeuralGalaxy.tsx`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/frontend/src/components/NeuralGalaxy.tsx): 2D/3D graph rendering
- [`frontend/src/hooks/useThoughtGraph.ts`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/frontend/src/hooks/useThoughtGraph.ts): core graph state
- [`frontend/src/hooks/useSocialLayer.ts`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/frontend/src/hooks/useSocialLayer.ts): social/report/snapshot state

## How It Works

### Thought analysis

Each thought is analyzed locally:

- text is embedded using a deterministic local representation
- emotion is inferred heuristically
- topics are inferred heuristically
- pairwise similarity is computed with cosine similarity

### Graph generation

- thoughts become nodes
- sufficiently similar thoughts become edges
- connected components become clusters
- clusters get labels, colors, themes, and trends

### Insight generation

Insights are derived from local graph statistics such as:

- dominant clusters
- emotional concentration
- recent changes in activity
- repeated themes

### Social overlay

When social view is enabled:

- followed users’ public thoughts are added as a second graph layer
- cross-user semantic links are generated
- reply links can appear across users
- social authors are represented separately from the user’s personal graph

## Repository Structure

```text
ThoughtGraph/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── hooks/
│   │   └── store/
│   └── package.json
└── README.md
```

## Local Development

### Requirements

- Python 3.11+
- Node.js 18+
- npm

### Backend setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend setup

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### Production build

```powershell
cd frontend
npm run build
```

## Environment Variables

### Backend

```text
THOUGHTGRAPH_DATABASE_URL=sqlite:///./thoughtgraph.db
THOUGHTGRAPH_CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173","http://localhost:4173","http://127.0.0.1:4173"]
THOUGHTGRAPH_DEFAULT_USER_ID=local-user
THOUGHTGRAPH_SEMANTIC_LINK_THRESHOLD=0.23
THOUGHTGRAPH_SEMANTIC_LINK_LIMIT=5
THOUGHTGRAPH_GRAPH_WINDOW_DAYS=30
```

### Frontend

```text
VITE_API_URL=http://localhost:8000
```

Examples are included in:

- [`backend/.env.example`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/backend/.env.example)
- [`frontend/.env.example`](C:/Users/Rounak/OneDrive/Desktop/Projects/ThoughtGraph/frontend/.env.example)

## Running the App

When both services are up:

- frontend: `http://127.0.0.1:5173`
- backend health: `http://127.0.0.1:8000/api/health`

Useful flows to try:

1. Load seeded mind from the sidebar.
2. Load the demo social network.
3. Toggle social view on.
4. Click a social node and reply.
5. Open explore, reports, profile, and settings.
6. Capture a snapshot and open its public route.

## API Surface

### Core V1-style endpoints

- `GET /api/graph`
- `GET /api/insights`
- `POST /api/thoughts`
- `POST /api/demo/seed`
- `GET /api/ws`

### Additive V2 endpoints

- `GET /api/graph?social=true`
- `GET /api/users/me`
- `PATCH /api/users/me`
- `PATCH /api/users/me/notification-preferences`
- `PATCH /api/users/me/onboarding`
- `PATCH /api/users/me/thought-visibility`
- `GET /api/users/me/export`
- `DELETE /api/users/me`
- `GET /api/users/search`
- `GET /api/users/{user_id}`
- `POST /api/social/follow/{user_id}`
- `DELETE /api/social/follow/{user_id}`
- `GET /api/social/feed`
- `GET /api/social/replies/{thought_id}`
- `GET /api/social/influence`
- `GET /api/social/influence/{user_id}`
- `GET /api/social/trending-clusters`
- `GET /api/social/suggested-users`
- `POST /api/social/demo/seed`
- `GET /api/notifications`
- `PATCH /api/notifications/{notification_id}`
- `POST /api/snapshots`
- `GET /api/snapshots`
- `GET /api/snapshots/recent/public`
- `GET /api/snapshots/public/{snapshot_id}`
- `DELETE /api/snapshots/{snapshot_id}`
- `POST /api/reports/generate`
- `GET /api/reports`
- `GET /api/reports/latest`
- `GET /api/reports/{report_id}`

## Testing

Backend tests:

```powershell
cd backend
.\.venv\Scripts\pytest
```

Frontend build validation:

```powershell
cd frontend
npm run build
```

Current status:

- backend tests pass
- frontend production build passes

## Design Notes

The current implementation is intentionally local-first.

That means:

- no API keys are required
- no external LLM provider is required
- no Redis, Celery, or Neo4j is required
- all core behavior works on SQLite and local heuristics

This is deliberate. The repo is structured so those systems can be introduced later without rewriting the client contract.

## Scalability Direction

The codebase is organized so it can evolve toward:

- PostgreSQL + Alembic migrations
- Redis caching
- Celery task queues for reports and snapshot rendering
- Neo4j for richer traversal and social graph queries
- external embedding and LLM providers
- stronger auth and multi-tenant identity

The current V2 code is a product-grade prototype and local platform foundation, not a finished distributed production deployment.

## Known Limitations

- influence scoring is heuristic, not model-backed
- snapshot and weekly report rendering use generated SVG data URIs, not object storage
- there is no real auth provider yet; user identity is resolved locally
- there is no browser E2E suite yet
- there is no production-grade async worker pipeline yet
- the frontend still ships a heavy `three` chunk
- load testing and launch-monitoring work are still operational tasks, not implemented infrastructure

## Why This Project Matters

Most software helps people publish, consume, or store information. Very little software helps people see the shape of their own mind.

ThoughtGraph is trying to make cognition legible:

- first to the self
- then in relation to others
- then as something that can be reflected on, shared, and improved

That is the real goal of the project.
