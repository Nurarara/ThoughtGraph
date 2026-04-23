from __future__ import annotations

from collections import Counter

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.cluster import Cluster
from app.models.friendship import Friendship
from app.models.thought import Thought
from app.models.user import User
from app.schemas.friendship import FriendsListResponse, FriendSummary
from app.services.notification_service import create_notification
from app.services.resonance_service import compute_resonance


def _public_top_clusters(session: Session, user_id: str) -> list[str]:
    rows = session.scalars(
        select(Thought.cluster_id).where(
            Thought.user_id == user_id,
            Thought.visibility == "public",
        )
    ).all()
    if not rows:
        return []
    labels = {
        cluster.id: cluster.label
        for cluster in session.scalars(select(Cluster).where(Cluster.user_id == user_id))
    }
    counts = Counter(cid for cid in rows if cid)
    return [labels[cid] for cid, _ in counts.most_common(3) if cid in labels]


def _summary(
    session: Session,
    user: User,
    status: str,
    since=None,
    *,
    current_user_id: str | None = None,
) -> FriendSummary:
    resonance_score: int | None = None
    shared_topics: list[str] = []
    if current_user_id and status == "accepted":
        resonance = compute_resonance(session, current_user_id, user.id, allow_friend_visibility=True)
        resonance_score = resonance.resonance_score
        shared_topics = resonance.shared_topics
    return FriendSummary(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        top_clusters=_public_top_clusters(session, user.id),
        status=status,
        since=since,
        resonance_score=resonance_score,
        shared_topics=shared_topics,
    )


def _find_friendship(session: Session, a: str, b: str) -> Friendship | None:
    return session.scalar(
        select(Friendship).where(
            or_(
                (Friendship.requester_id == a) & (Friendship.addressee_id == b),
                (Friendship.requester_id == b) & (Friendship.addressee_id == a),
            )
        )
    )


def request_friend(session: Session, requester_id: str, addressee_id: str) -> FriendSummary:
    if requester_id == addressee_id:
        raise ValueError("cannot friend yourself")
    addressee = session.get(User, addressee_id)
    if addressee is None:
        raise ValueError("user not found")
    existing = _find_friendship(session, requester_id, addressee_id)
    notify_target: str | None = None
    notify_type: str | None = None
    if existing is None:
        existing = Friendship(
            requester_id=requester_id,
            addressee_id=addressee_id,
            status="pending",
        )
        session.add(existing)
        notify_target, notify_type = addressee_id, "friend_request"
    elif existing.status == "accepted":
        pass
    elif existing.status == "pending" and existing.requester_id == addressee_id:
        existing.status = "accepted"
        notify_target, notify_type = existing.requester_id, "friend_accept"
    else:
        existing.requester_id = requester_id
        existing.addressee_id = addressee_id
        existing.status = "pending"
        notify_target, notify_type = addressee_id, "friend_request"
    session.commit()
    session.refresh(existing)
    if notify_target and notify_type:
        create_notification(
            session,
            user_id=notify_target,
            notification_type=notify_type,
            actor_id=requester_id,
            content="",
        )
    return _summary(session, addressee, existing.status, existing.updated_at, current_user_id=requester_id)


def respond_friend(session: Session, current_user_id: str, requester_id: str, accept: bool) -> FriendSummary | None:
    record = _find_friendship(session, current_user_id, requester_id)
    if record is None or record.addressee_id != current_user_id:
        return None
    requester = session.get(User, requester_id)
    if requester is None:
        return None
    record.status = "accepted" if accept else "declined"
    session.commit()
    session.refresh(record)
    if accept:
        create_notification(
            session,
            user_id=requester_id,
            notification_type="friend_accept",
            actor_id=current_user_id,
            content="",
        )
    return _summary(session, requester, record.status, record.updated_at, current_user_id=current_user_id)


def list_friends(session: Session, current_user_id: str) -> FriendsListResponse:
    rows = session.scalars(
        select(Friendship).where(
            or_(
                Friendship.requester_id == current_user_id,
                Friendship.addressee_id == current_user_id,
            )
        )
    ).all()
    friends: list[FriendSummary] = []
    incoming: list[FriendSummary] = []
    outgoing: list[FriendSummary] = []
    for row in rows:
        other_id = row.addressee_id if row.requester_id == current_user_id else row.requester_id
        other = session.get(User, other_id)
        if other is None:
            continue
        summary = _summary(session, other, row.status, row.updated_at, current_user_id=current_user_id)
        if row.status == "accepted":
            friends.append(summary)
        elif row.status == "pending":
            if row.addressee_id == current_user_id:
                incoming.append(summary)
            else:
                outgoing.append(summary)
    return FriendsListResponse(friends=friends, incoming=incoming, outgoing=outgoing)


def suggest_friends(session: Session, current_user_id: str, limit: int = 12) -> list[FriendSummary]:
    existing = set(accepted_friend_ids(session, current_user_id))
    pending = {
        row.addressee_id if row.requester_id == current_user_id else row.requester_id
        for row in session.scalars(
            select(Friendship).where(
                or_(
                    Friendship.requester_id == current_user_id,
                    Friendship.addressee_id == current_user_id,
                )
            )
        )
    }
    excluded = existing | pending | {current_user_id}

    my_clusters = set(_public_top_clusters(session, current_user_id))

    fof_scores: dict[str, int] = {}
    for friend_id in existing:
        for foaf in accepted_friend_ids(session, friend_id):
            if foaf in excluded:
                continue
            fof_scores[foaf] = fof_scores.get(foaf, 0) + 2

    candidates = list(
        session.scalars(
            select(User).where(User.is_public.is_(True)).limit(200)
        )
    )
    scored: list[tuple[int, User]] = []
    for user in candidates:
        if user.id in excluded:
            continue
        overlap_score = 0
        if my_clusters:
            their_clusters = set(_public_top_clusters(session, user.id))
            overlap_score = len(my_clusters & their_clusters)
        total = fof_scores.get(user.id, 0) + overlap_score
        if total > 0 or user.id in fof_scores:
            scored.append((total, user))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [
        _summary(session, user, "suggested")
        for _, user in scored[:limit]
    ]


def accepted_friend_ids(session: Session, user_id: str) -> list[str]:
    rows = session.scalars(
        select(Friendship).where(
            (Friendship.status == "accepted")
            & or_(
                Friendship.requester_id == user_id,
                Friendship.addressee_id == user_id,
            )
        )
    ).all()
    return [row.addressee_id if row.requester_id == user_id else row.requester_id for row in rows]
