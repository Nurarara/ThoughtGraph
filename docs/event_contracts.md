# Event Contracts

Every important mutation emits an internal event with:

- `event_type`
- `aggregate_type`
- `aggregate_id`
- `actor_id`
- `payload`
- `created_at`

## Active events in Phase 1-2

### `user_registered`
- Aggregate: `user`
- Trigger: first verified login

### `profile_updated`
- Aggregate: `profile`
- Trigger: profile patch accepted

### `node_created`
- Aggregate: `content_node`
- Trigger: node persisted

### `media_registered`
- Aggregate: `media_asset`
- Trigger: image asset metadata persisted

### `graph_job_enqueued`
- Aggregate: `workflow_job`
- Trigger: graph recompute job created

### `node_embedded`
- Aggregate: `content_node`
- Trigger: embedding generated for a node

### `edge_created`
- Aggregate: `node_edge`
- Trigger: semantic edge created or upserted

### `cluster_updated`
- Aggregate: `node_cluster`
- Trigger: connected component reclustered

### `graph_projection_refreshed`
- Aggregate: `content_node`
- Trigger: local neighborhood recompute completed

## Reserved event names for later phases

- `follow_created`
- `friendship_requested`
- `friendship_accepted`
- `reaction_added`
- `claim_flagged`
- `provenance_updated`
- `recommendation_materialized`

## Compatibility rule

Business meaning is stable even if transport changes later from in-process persistence to Kafka.
