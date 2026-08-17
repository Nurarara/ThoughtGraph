# ThoughtGraph Phase 6-12 Verification

This document is the prototype acceptance checklist for the later system layers. The implementation remains a modular monolith: Postgres is the intended canonical store, while local development can still run on SQLite. Kafka, Temporal, OpenSearch, and Neo4j are represented by explicit boundaries and rebuildable read models, not by pretending those clusters are deployed.

## Phase 6 - Event Bus And Async Fan-Out

- Canonical event log remains `domain_events`.
- In-process consumer registry lives behind `GLOBAL_EVENT_BUS`.
- Consumer checkpoints and dead letters are persisted in infra tables.
- Replay APIs exist for dead-letter recovery.
- Prototype endpoints:
  - `POST /api/infra/events/dispatch`
  - `GET /api/infra/dead-letters`
  - `POST /api/infra/dead-letters/replay`

Acceptance command:

```powershell
python -m pytest backend/app/tests/test_infra_phase.py -q
```

## Phase 7 - Search And Discovery Scale-Out Boundary

- Search documents are derived from canonical `content_nodes` and legacy `thoughts`.
- Rebuilds can delete and regenerate the read model.
- Search scoring is explainable: lexical score, semantic score, total score, matched terms.
- Prototype endpoints:
  - `POST /api/infra/search/rebuild`
  - `GET /api/infra/search?q=...`

## Phase 8 - Provenance And Trust

- Claims, sources, evidence, rationale versions, and provenance snapshots are first-class canonical tables.
- Trust scores are versioned through rationale records.
- Provenance reads return inspectable graph JSON plus source/evidence summaries.
- Prototype endpoints:
  - `POST /api/trust/claims`
  - `POST /api/trust/sources`
  - `POST /api/trust/claims/{claim_id}/evidence`
  - `POST /api/trust/claims/{claim_id}/rationales`
  - `GET /api/trust/claims/{claim_id}/provenance`
  - `GET /api/trust/nodes/{node_id}/provenance`

## Phase 9 - Graph Read Model Specialization Boundary

- Graph read model tables are derived from canonical content nodes and node edges.
- Writes still originate from canonical services.
- Rebuilds are explicit and projection runs are audited.
- Prototype endpoints:
  - `POST /api/infra/graph/rebuild`
  - `GET /api/infra/graph`

## Phase 10 - Reflective Insights

- Weekly reports and reflective insights are generated from visible graph evidence.
- Insight payloads include metrics, evidence references, and action hints.
- Runs can execute inline for prototype or queue through `workflow_jobs`.
- Prototype endpoint:
  - `POST /api/reflective-insights/run`

## Phase 11 - Moderation And Abuse Controls

- Reports, moderation event logs, and enforcement states are first-class tables.
- Enforcement can block nodes from discovery without deleting canonical content.
- Discovery filters out moderation-blocked nodes.
- Prototype endpoints:
  - `POST /api/moderation/reports`
  - `POST /api/moderation/reports/{report_id}/resolve`
  - `PUT /api/moderation/enforcement`
  - `GET /api/moderation/enforcement/{subject_type}/{subject_id}`
  - `GET /api/moderation/events`

## Phase 12 - Scale Hardening And Ops

- Ops status exposes partition-like grouping, SLO freshness, dead-letter backlog, and replay readiness.
- This is a prototype dashboard over local tables; production still needs real Postgres migrations and observability wiring.
- Prototype endpoints:
  - `GET /api/infra/ops/status`
  - `GET /api/infra/ops/replay-readiness`

## Full Prototype Gate

Run these before publishing a prototype:

```powershell
python -m pytest backend/app/tests -q
cd frontend
npm run build
```

Current integrated route coverage is in `backend/app/tests/test_api.py` under `test_phase_6_to_12_routes_are_mounted_and_explainable`.
