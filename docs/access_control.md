# Access Control

## Phase 1-2 rules

### Identity
- Anonymous users may request a magic link.
- Verified users receive a session token.
- Every authenticated request resolves to exactly one user.

### Profile visibility
- Public profile: display name, bio, created-at visibility, graph summary counts
- Private profile: visible in full only to owner

### Node visibility
- `private`: visible only to owner
- `public`: visible to everyone with a valid request context

### Read rules
- Graph reads only return nodes the requester can see.
- Cluster counts and search results are visibility-filtered.
- Node detail payloads cannot expose hidden neighbors.

### Write rules
- Users can only mutate their own profile and nodes.
- Media assets are bound to the creating user.
- Jobs and events are internal-only surfaces.

## Later-phase reserved scopes

- `friends`
- `custom_audience`
- `restricted`

Those scopes are named now to avoid future vocabulary drift, but they are not active before Phase 3.
