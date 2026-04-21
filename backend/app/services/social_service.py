from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.follow import Follow
from app.models.thought import Thought
from app.models.user import User
from app.schemas.social import (
    FollowListItem,
    ReplyThreadRead,
    SocialFeedItem,
    SocialRelationship,
    SocialReplyRead,
    TrendingClusterRead,
)
from app.services.broadcast import manager
from app.services.graph_pipeline import analyze_thought_content, ensure_utc, recompute_graph
from app.services.notification_service import create_notification
from app.services.text_analysis import cosine_similarity
from app.services.user_service import ensure_user_exists


def get_following_ids(session: Session, user_id: str) -> list[str]:
    return list(session.scalars(select(Follow.following_id).where(Follow.follower_id == user_id)))


def get_followers_ids(session: Session, user_id: str) -> list[str]:
    return list(session.scalars(select(Follow.follower_id).where(Follow.following_id == user_id)))


async def follow_user(session: Session, follower_id: str, target_id: str) -> bool:
    if follower_id == target_id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    follower = ensure_user_exists(session, follower_id)
    target = ensure_user_exists(session, target_id)
    existing = session.scalar(
        select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == target_id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already following")

    session.add(Follow(follower_id=follower_id, following_id=target_id))
    follower.following_count += 1
    target.follower_count += 1
    session.add_all([follower, target])
    session.commit()

    notification = create_notification(
        session,
        target_id,
        "new_follower",
        actor_id=follower_id,
        content=f"{follower.display_name} started following you.",
    )
    if notification.id != "suppressed":
        await manager.send_to_user(
            target_id,
            {
                "type": "new_follower",
                "user_id": follower_id,
                "display_name": follower.display_name,
                "notification_id": notification.id,
            },
        )
    return True


def unfollow_user(session: Session, follower_id: str, target_id: str) -> bool:
    follow = session.scalar(
        select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == target_id)
    )
    if not follow:
        return False

    follower = ensure_user_exists(session, follower_id)
    target = ensure_user_exists(session, target_id)
    follower.following_count = max(0, follower.following_count - 1)
    target.follower_count = max(0, target.follower_count - 1)
    session.delete(follow)
    session.add_all([follower, target])
    session.commit()
    return False


def get_relationship(session: Session, current_user_id: str, target_user_id: str) -> SocialRelationship:
    following = session.scalar(
        select(Follow).where(Follow.follower_id == current_user_id, Follow.following_id == target_user_id)
    )
    followed_by = session.scalar(
        select(Follow).where(Follow.follower_id == target_user_id, Follow.following_id == current_user_id)
    )
    return SocialRelationship(following=following is not None, followed_by=followed_by is not None)


def _build_follow_list_items(session: Session, follows: list[Follow], *, followers: bool) -> list[FollowListItem]:
    user_ids = [follow.follower_id if followers else follow.following_id for follow in follows]
    users = {user.id: user for user in session.scalars(select(User).where(User.id.in_(user_ids)))}

    cluster_map: dict[str, list[str]] = defaultdict(list)
    thoughts = list(session.scalars(select(Thought).where(Thought.user_id.in_(user_ids))))
    for thought in thoughts:
        for topic in thought.topics[:1]:
            if topic not in cluster_map[thought.user_id]:
                cluster_map[thought.user_id].append(topic)

    items = []
    for follow in follows:
        user_id = follow.follower_id if followers else follow.following_id
        user = users.get(user_id)
        if not user:
            continue
        items.append(
            FollowListItem(
                user_id=user.id,
                display_name=user.display_name,
                avatar_url=user.avatar_url,
                top_clusters=cluster_map.get(user.id, [])[:3],
                followed_at=follow.created_at,
            )
        )
    return items


def list_followers(session: Session, user_id: str) -> list[FollowListItem]:
    follows = list(
        session.scalars(
            select(Follow).where(Follow.following_id == user_id).order_by(desc(Follow.created_at))
        )
    )
    return _build_follow_list_items(session, follows, followers=True)


def list_following(session: Session, user_id: str) -> list[FollowListItem]:
    follows = list(
        session.scalars(
            select(Follow).where(Follow.follower_id == user_id).order_by(desc(Follow.created_at))
        )
    )
    return _build_follow_list_items(session, follows, followers=False)


def seed_social_demo(session: Session, current_user_id: str) -> dict[str, int]:
    demo_users = [
        {
            "id": "maya-chen",
            "display_name": "Maya Chen",
            "bio": "Builds humane AI products and overthinks influence.",
            "thoughts": [
                "I keep wondering whether AI products should optimize for clarity instead of endless engagement.",
                "Most product strategy mistakes are really just unspoken incentives becoming interface decisions.",
                "I notice I trust systems more when they reveal uncertainty instead of hiding it.",
            ],
        },
        {
            "id": "leo-martin",
            "display_name": "Leo Martin",
            "bio": "Thinking in public about policy, economics, and information systems.",
            "thoughts": [
                "Politics has become a competition over attention architecture more than ideology.",
                "People call it polarization, but a lot of it is repeated exposure to emotionally efficient narratives.",
                "Economic anxiety keeps leaking into every conversation about technology.",
            ],
        },
        {
            "id": "sana-rivera",
            "display_name": "Sana Rivera",
            "bio": "Writes about health, discipline, and creative resilience.",
            "thoughts": [
                "Sleep is the first place my discipline collapses when ambition gets performative.",
                "Creative work gets easier when I stop asking whether it will matter and just make the next honest thing.",
                "Health routines are easier to keep when they become identity instead of chores.",
            ],
        },
    ]

    created_users = 0
    created_thoughts = 0
    for payload in demo_users:
        user = session.get(User, payload["id"])
        if not user:
            user = User(
                id=payload["id"],
                display_name=payload["display_name"],
                bio=payload["bio"],
                is_public=True,
            )
            session.add(user)
            created_users += 1
            session.commit()

        existing_thought = session.scalar(select(Thought).where(Thought.user_id == payload["id"]))
        if existing_thought:
            continue

        for content in payload["thoughts"]:
            vector, emotion, topics = analyze_thought_content(content)
            session.add(
                Thought(
                    user_id=payload["id"],
                    content=content,
                    emotion=emotion,
                    topics=topics,
                    vector=vector,
                    visibility="public",
                    created_at=datetime.now(timezone.utc),
                )
            )
            created_thoughts += 1
        session.commit()
        recompute_graph(session, payload["id"])

    ensure_user_exists(session, current_user_id)
    return {"users_created": created_users, "thoughts_created": created_thoughts}


def _serialize_reply(session: Session, thought: Thought) -> SocialReplyRead:
    author = ensure_user_exists(session, thought.user_id)
    return SocialReplyRead(
        id=thought.id,
        content=thought.content,
        created_at=thought.created_at,
        emotion=thought.emotion,
        topics=thought.topics,
        author_id=author.id,
        author_display_name=author.display_name,
        visibility=thought.visibility,
        reply_to_id=thought.reply_to_id,
        reply_to_user_id=thought.reply_to_user_id,
    )


def get_reply_thread(session: Session, current_user_id: str, thought_id: str) -> ReplyThreadRead:
    root = session.get(Thought, thought_id)
    if not root:
        raise HTTPException(status_code=404, detail="Thought not found")
    if root.visibility == "private" and root.user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Thought not found")

    replies = list(
        session.scalars(select(Thought).where(Thought.reply_to_id == thought_id).order_by(Thought.created_at.asc()))
    )
    visible_replies = [reply for reply in replies if reply.visibility == "public" or reply.user_id == current_user_id]
    return ReplyThreadRead(
        root=_serialize_reply(session, root),
        replies=[_serialize_reply(session, reply) for reply in visible_replies],
    )


def list_social_feed(session: Session, user_id: str, limit: int = 20) -> list[SocialFeedItem]:
    following_ids = get_following_ids(session, user_id)
    if not following_ids:
        return []
    thoughts = list(
        session.scalars(
            select(Thought)
            .where(Thought.user_id.in_(following_ids), Thought.visibility == "public")
            .order_by(desc(Thought.created_at))
            .limit(limit)
        )
    )
    return [
        SocialFeedItem(
            thought=_serialize_reply(session, thought),
            relationship="reply" if thought.reply_to_user_id == user_id else "ambient",
        )
        for thought in thoughts
    ]


def get_trending_clusters(session: Session, limit: int = 10) -> list[TrendingClusterRead]:
    public_user_ids = [user.id for user in session.scalars(select(User).where(User.is_public.is_(True)))]
    if not public_user_ids:
        return []

    thoughts = list(
        session.scalars(select(Thought).where(Thought.user_id.in_(public_user_ids), Thought.visibility == "public"))
    )
    if not thoughts:
        return []

    now = datetime.now(timezone.utc)
    current_cutoff = now - timedelta(days=7)
    previous_cutoff = now - timedelta(days=14)
    labels_to_thoughts: dict[str, list[Thought]] = defaultdict(list)
    for thought in thoughts:
        label = " / ".join(topic.replace("_", " ").title() for topic in thought.topics[:2]) or "General Reflection"
        labels_to_thoughts[label].append(thought)

    rows: list[TrendingClusterRead] = []
    for label, label_thoughts in labels_to_thoughts.items():
        current_count = sum(ensure_utc(thought.created_at) >= current_cutoff for thought in label_thoughts)
        previous_count = sum(
            previous_cutoff <= ensure_utc(thought.created_at) < current_cutoff for thought in label_thoughts
        )
        growth_percentage = round(((current_count - previous_count) / max(previous_count, 1)) * 100, 2)
        rows.append(
            TrendingClusterRead(
                label=label,
                growth_percentage=growth_percentage,
                user_count=len({thought.user_id for thought in label_thoughts}),
                thought_count=len(label_thoughts),
                sample_thoughts=[thought.content[:120] for thought in label_thoughts[:3]],
            )
        )
    rows.sort(key=lambda item: (item.growth_percentage, item.user_count, item.thought_count), reverse=True)
    return rows[:limit]


def _top_topics_for_user(session: Session, user_id: str) -> list[str]:
    thoughts = list(session.scalars(select(Thought).where(Thought.user_id == user_id, Thought.visibility == "public")))
    counts = Counter(topic for thought in thoughts for topic in thought.topics)
    return [topic.replace("_", " ").title() for topic, _ in counts.most_common(3)]


def get_suggested_users(session: Session, user_id: str, limit: int = 10) -> list[FollowListItem]:
    following_ids = set(get_following_ids(session, user_id))
    own_thoughts = list(session.scalars(select(Thought).where(Thought.user_id == user_id)))
    own_topics = Counter(topic for thought in own_thoughts for topic in thought.topics)
    candidates = list(
        session.scalars(select(User).where(User.id != user_id, User.is_public.is_(True)).order_by(User.follower_count.desc()))
    )
    scored: list[tuple[float, User]] = []
    for candidate in candidates:
        if candidate.id in following_ids:
            continue
        candidate_thoughts = list(
            session.scalars(select(Thought).where(Thought.user_id == candidate.id, Thought.visibility == "public"))
        )
        if not candidate_thoughts:
            continue
        candidate_topics = Counter(topic for thought in candidate_thoughts for topic in thought.topics)
        shared_topics = sum(min(own_topics[topic], candidate_topics[topic]) for topic in own_topics if topic in candidate_topics)
        if own_thoughts:
            shared_vector = 0.0
            comparisons = 0
            for own in own_thoughts[:10]:
                best = max((cosine_similarity(own.vector, other.vector) for other in candidate_thoughts[:10]), default=0.0)
                shared_vector += best
                comparisons += 1
            similarity = shared_vector / max(comparisons, 1)
        else:
            similarity = candidate.follower_count / 100.0
        score = similarity + shared_topics * 0.05 + min(candidate.follower_count, 50) * 0.01
        scored.append((score, candidate))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        FollowListItem(
            user_id=user.id,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            top_clusters=_top_topics_for_user(session, user.id),
            followed_at=user.created_at,
        )
        for _, user in scored[:limit]
    ]
