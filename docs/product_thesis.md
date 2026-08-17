# ThoughtGraph Product Thesis

ThoughtGraph is a graph-native social platform where posts, links, images, replies, and later claims/sources are first-class nodes inside a living map instead of entries in a vertical feed.

## Core product claim

The primary interaction is spatial exploration. Users should navigate meaning by panning, zooming, focusing, expanding, and tracing relationships rather than passively consuming an opaque ranking stream.

## Product layers

1. Personal graph: a user's posts and media form a living map of interests, themes, and recurring patterns.
2. Social graph: relationships between people and topics create adjacent neighborhoods rather than a global feed.
3. Discovery layer: recommendations must carry explanation metadata and expose why a node is visible.
4. Trust and provenance layer: claims, sources, evidence, and spread paths are inspectable later-phase graph entities.

## System posture through Phase 2

- Modular monolith first.
- Postgres is the target source of truth, with local SQLite fallback only for development and tests.
- The graph is modeled relationally first.
- Every important mutation emits a structured internal event.
- Expensive recomputation happens through a durable job boundary, even when executed inline in development.
- The frontend is graph-first, not feed-first.
