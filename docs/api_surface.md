# ThoughtGraph API Surface

The active API is mounted from `backend/app/api/router.py`.

Active route modules:

- `auth`
- `discovery`
- `friends`
- `graph`
- `infra`
- `media`
- `nodes`
- `reflective_insights`
- `social`
- `trust_moderation`
- `users`

Legacy route modules from the earlier feed-style prototype may still exist on disk while the project is being migrated. They are not part of the active graph-native API unless they are explicitly mounted in `api/router.py`.

Current frontend code should use `graphApi` from `frontend/src/lib/apiClient.ts`. The old feed/social client is exposed as `legacyThoughtApi` only for inactive legacy screens.
