from fastapi import APIRouter

from app.api.routes import (
    auth,
    discovery,
    friends,
    graph,
    infra,
    media,
    nodes,
    reflective_insights,
    social,
    trust_moderation,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(discovery.router, tags=["discovery"])
api_router.include_router(friends.router, tags=["friends"])
api_router.include_router(graph.router, tags=["graph"])
api_router.include_router(infra.router, tags=["infra"])
api_router.include_router(media.router, tags=["media"])
api_router.include_router(nodes.router, tags=["nodes"])
api_router.include_router(reflective_insights.router, tags=["reflective-insights"])
api_router.include_router(social.router, tags=["social"])
api_router.include_router(trust_moderation.router, tags=["trust-moderation"])
api_router.include_router(users.router, tags=["users"])
