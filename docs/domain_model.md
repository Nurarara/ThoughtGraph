# Domain Model

This document freezes the Phase 0-2 ontology.

## Canonical entities

### User
- Owner: self
- Lifecycle: invited/request-link -> verified -> active -> deleted
- Visibility: public profile or private profile
- Notes: canonical identity and policy subject

### Profile
- Owner: user
- Lifecycle: created with user -> updated over time
- Visibility: public fields are policy-controlled; private fields visible only to owner
- Notes: display name, bio, onboarding state, profile preferences

### ContentNode
- Owner: user
- Lifecycle: created -> embedded -> clustered -> updated -> archived/deleted
- Visibility: private or public in Phase 1-2
- Kinds in scope now: `thought`, `image`, `link`
- Notes: canonical authored content object for the graph

### MediaAsset
- Owner: user
- Lifecycle: registered -> ready -> failed -> deleted
- Visibility: inherited from referencing node
- Notes: Phase 1 supports externally referenced images; direct uploads come later

### NodeEdge
- Owner: derived from user graph
- Lifecycle: created/updated by graph recompute -> removed when invalidated
- Visibility: inherited from endpoint nodes
- Kinds in scope now: `semantic_similarity`

### NodeCluster
- Owner: derived from user graph
- Lifecycle: created/updated/merged by local graph recompute
- Visibility: inherited from endpoint nodes
- Notes: lightweight local grouping, not a global community model

### WorkflowJob
- Owner: system
- Lifecycle: pending -> running -> completed | failed
- Visibility: internal
- Notes: boundary for expensive or retryable work

### DomainEvent
- Owner: system
- Lifecycle: emitted -> stored -> replayable
- Visibility: internal
- Notes: event-first contract that derived systems can consume later

## Deferred entities

The following names are reserved but intentionally not implemented in runtime behavior before Phase 3+:

- Follow
- Friendship
- Interaction
- FeedItem
- Claim
- Source
- Evidence
- ProvenanceLink
- Notification
- Report
- Snapshot

## Service boundaries inside the modular monolith

- Identity service: authentication session issuance and user bootstrap
- Profile service: profile reads and writes, onboarding state
- Content service: node creation and validation
- Media service: external image asset registration abstraction
- Graph service: embeddings, similarity edges, connected components, graph reads
- Search service: graph and profile search-to-focus
- Event service: canonical internal event emission
- Workflow service: durable local job boundary
