from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models.thought import Thought
from app.schemas.thought import ThoughtCreate, ThoughtRead
from app.services.broadcast import manager
from app.services.graph_pipeline import analyze_thought_content, get_graph_response_with_options, recompute_graph
from app.services.influence_service import compute_influence_pair
from app.services.insight_engine import refresh_insights
from app.services.notification_service import create_notification
from app.services.social_service import seed_social_demo
from app.services.user_service import ensure_user_exists

router = APIRouter()


@router.post("/thoughts", response_model=ThoughtRead)
async def create_thought(
    payload: ThoughtCreate,
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> ThoughtRead:
    ensure_user_exists(session, current_user_id)
    vector, emotion, topics = analyze_thought_content(payload.content)
    reply_to_user_id = None
    if payload.reply_to_id:
        reply_target = session.scalar(select(Thought).where(Thought.id == payload.reply_to_id))
        if not reply_target:
            raise HTTPException(status_code=404, detail="Reply target not found")
        reply_to_user_id = reply_target.user_id

    thought = Thought(
        user_id=current_user_id,
        content=payload.content.strip(),
        created_at=datetime.now(timezone.utc),
        emotion=emotion,
        topics=topics,
        vector=vector,
        visibility=payload.visibility,
        reply_to_id=payload.reply_to_id,
        reply_to_user_id=reply_to_user_id,
    )
    session.add(thought)
    session.commit()
    session.refresh(thought)

    recompute_graph(session, current_user_id)
    created_insights = refresh_insights(session, current_user_id)
    refreshed = session.scalar(select(Thought).where(Thought.id == thought.id))
    graph = get_graph_response_with_options(session, current_user_id, social=False)

    if reply_to_user_id and reply_to_user_id != current_user_id:
        reply_notification = create_notification(
            session,
            reply_to_user_id,
            "reply",
            actor_id=current_user_id,
            thought_id=thought.id,
            content=f"{ensure_user_exists(session, current_user_id).display_name} replied to your thought.",
        )
        if reply_notification.id != "suppressed":
            await manager.send_to_user(
                reply_to_user_id,
                {
                    "type": "new_reply",
                    "thought_id": payload.reply_to_id,
                    "reply_id": thought.id,
                    "user_id": current_user_id,
                    "content_preview": thought.content[:120],
                    "notification_id": reply_notification.id,
                },
            )
        influence, milestone_crossed = compute_influence_pair(
            session,
            current_user_id,
            reply_to_user_id,
            create_milestone=True,
        )
        if milestone_crossed:
            influence_notification = create_notification(
                session,
                current_user_id,
                "influence_milestone",
                actor_id=reply_to_user_id,
                content=f"{influence.target_display_name} is now a strong influence on your graph.",
            )
            if influence_notification.id != "suppressed":
                await manager.send_to_user(
                    current_user_id,
                    {
                        "type": "influence_updated",
                        "target_user_id": reply_to_user_id,
                        "new_score": influence.score,
                        "notification_id": influence_notification.id,
                    },
                )

    await manager.send_to_user(
        current_user_id,
        {
            "type": "graph_updated",
            "nodeCount": len(graph.nodes),
            "edgeCount": len(graph.edges),
            "newInsights": len(created_insights),
        }
    )
    return ThoughtRead.model_validate(refreshed)


@router.post("/demo/seed")
async def seed_demo(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, int]:
    existing = session.scalar(select(Thought).where(Thought.user_id == current_user_id))
    if existing:
        return {"created": 0}

    seed_thoughts = [
        "I keep thinking about whether I should stay in this job or build something of my own.",
        "The AI tooling space is moving so quickly that I feel excited and slightly behind at the same time.",
        "My late-night scrolling always drags me back into politics and leaves me more tense than informed.",
        "I want my health to stop being a background concern and start becoming part of my identity.",
        "Money is not the real issue. I want freedom, and I keep translating that into money by habit.",
        "When I write clearly, I feel calmer. Maybe creativity is less hobby and more stabilizer.",
        "I am noticing that most of my ambition is really fear wearing a respectable suit.",
        "The product ideas that stay with me are always the ones that make people feel seen.",
        "I need a system that rewards focus instead of feeding the part of me that wants novelty every ten minutes.",
        "The people around me influence my confidence more than I admit.",
    ]
    for content in seed_thoughts:
        vector, emotion, topics = analyze_thought_content(content)
        session.add(
            Thought(
                user_id=current_user_id,
                content=content,
                emotion=emotion,
                topics=topics,
                vector=vector,
                visibility="public",
            )
        )
    session.commit()
    recompute_graph(session, current_user_id)
    refresh_insights(session, current_user_id)
    return {"created": len(seed_thoughts)}


@router.post("/social/demo/seed")
async def seed_social_demo_route(
    session: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
) -> dict[str, int]:
    return seed_social_demo(session, current_user_id)
