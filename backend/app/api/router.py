from fastapi import APIRouter

from app.api.routes import (
    auth,
    friends,
    graph,
    insights,
    notifications,
    posts,
    reports,
    snapshots,
    social,
    thoughts,
    users,
    websocket,
)

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(graph.router, tags=["graph"])
api_router.include_router(thoughts.router, tags=["thoughts"])
api_router.include_router(insights.router, tags=["insights"])
api_router.include_router(users.router, tags=["users"])
api_router.include_router(social.router, tags=["social"])
api_router.include_router(friends.router, tags=["friends"])
api_router.include_router(posts.router, tags=["posts"])
api_router.include_router(notifications.router, tags=["notifications"])
api_router.include_router(snapshots.router, tags=["snapshots"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(websocket.router, tags=["ws"])
