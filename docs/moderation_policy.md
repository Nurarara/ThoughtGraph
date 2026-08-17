# Moderation Policy

Phase 0-2 moderation is intentionally minimal but explicit.

## Goals

- Preserve auditable state changes.
- Avoid content-policy ambiguity in the data model.
- Keep room for later trust, safety, and enforcement systems.

## Current controls

- Canonical ownership on every user-authored record
- Stored event log for important mutations
- Node visibility controls (`private`, `public`)
- Job and event replay surfaces for debugging and future enforcement

## Deliberately deferred

- Reports
- Block/mute flows
- Automated spam scoring
- Appeals
- Takedown tooling
- Provenance verification decisions

## Constraint

Nothing in Phase 1-2 should make later moderation impossible. Hidden side effects, denormalized write-only caches, and implicit audience logic are not allowed.
