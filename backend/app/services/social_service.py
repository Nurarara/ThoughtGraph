from __future__ import annotations

from collections import Counter

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.content_node import ContentNode
from app.models.follow import Follow
from app.models.friendship import Friendship
from app.models.node_cluster import NodeCluster
from app.models.user import User
from app.models.user_restriction import UserRestriction
from app.schemas.social import (
    FriendshipListItem,
    FriendshipListsRead,
    SocialNeighborhoodItem,
    SocialNeighborhoodResponse,
    SocialProfileRead,
    SocialRelationshipRead,
)
from app.schemas.user import UserSearchResult
from app.services.event_service import emit_event
from app.services.user_service import ensure_user_exists


def restriction_active(session: Session, source_user_id: str, target_user_id: str, kind: str) -> bool:
    return (
        session.scalar(
            select(UserRestriction).where(
                UserRestriction.source_user_id == source_user_id,
                UserRestriction.target_user_id == target_user_id,
                UserRestriction.kind == kind,
            )
        )
        is not None
    )


def blocked_between(session: Session, a: str, b: str) -> bool:
    return restriction_active(session, a, b, "blocked") or restriction_active(session, b, a, "blocked")


def muted_by(session: Session, source_user_id: str, target_user_id: str) -> bool:
    return restriction_active(session, source_user_id, target_user_id, "muted")


def restricted_by(session: Session, source_user_id: str, target_user_id: str) -> bool:
    return restriction_active(session, source_user_id, target_user_id, "restricted")


def get_friendship_record(session: Session, a: str, b: str) -> Friendship | None:
    return session.scalar(
        select(Friendship).where(
            or_(
                (Friendship.requester_id == a) & (Friendship.addressee_id == b),
                (Friendship.requester_id == b) & (Friendship.addressee_id == a),
            )
        )
    )


def friendship_state_for(session: Session, viewer_id: str, target_user_id: str) -> str:
    record = get_friendship_record(session, viewer_id, target_user_id)
    if record is None:
        return "none"
    if record.status == "accepted":
        return "accepted"
    if record.status == "pending":
        return "incoming" if record.addressee_id == viewer_id else "outgoing"
    return record.status


def are_friends(session: Session, a: str, b: str) -> bool:
    record = get_friendship_record(session, a, b)
    return record is not None and record.status == "accepted"


def get_following_ids(session: Session, user_id: str) -> list[str]:
    return list(session.scalars(select(Follow.following_id).where(Follow.follower_id == user_id)))


def get_follower_ids(session: Session, user_id: str) -> list[str]:
    return list(session.scalars(select(Follow.follower_id).where(Follow.following_id == user_id)))


def get_relationship(session: Session, viewer_id: str, target_user_id: str) -> SocialRelationshipRead:
    return SocialRelationshipRead(
        target_user_id=target_user_id,
        following=target_user_id in set(get_following_ids(session, viewer_id)),
        followed_by=target_user_id in set(get_follower_ids(session, viewer_id)),
        friendship_state=friendship_state_for(session, viewer_id, target_user_id),
        blocked=restriction_active(session, viewer_id, target_user_id, "blocked"),
        muted=restriction_active(session, viewer_id, target_user_id, "muted"),
        restricted=restriction_active(session, viewer_id, target_user_id, "restricted"),
        blocked_by_target=restriction_active(session, target_user_id, viewer_id, "blocked"),
        restricted_by_target=restriction_active(session, target_user_id, viewer_id, "restricted"),
    )


def can_view_profile(session: Session, viewer_id: str, target_user_id: str) -> bool:
    if viewer_id == target_user_id:
        return True
    if blocked_between(session, viewer_id, target_user_id):
        return False
    target = ensure_user_exists(session, target_user_id)
    return target.is_public or are_friends(session, viewer_id, target_user_id)


def can_view_node(session: Session, viewer_id: str, node: ContentNode) -> bool:
    if viewer_id == node.user_id:
        return True
    if blocked_between(session, viewer_id, node.user_id):
        return False
    if node.visibility == "public":
        return True
    if node.visibility == "friends":
        return are_friends(session, viewer_id, node.user_id) and not restricted_by(session, node.user_id, viewer_id)
    return False


def visible_nodes_for_owner(
    session: Session,
    viewer_id: str,
    owner_user_id: str,
    *,
    include_muted: bool = False,
) -> list[ContentNode]:
    if viewer_id != owner_user_id and muted_by(session, viewer_id, owner_user_id) and not include_muted:
        return []
    nodes = list(
        session.scalars(
            select(ContentNode).where(ContentNode.user_id == owner_user_id).order_by(ContentNode.created_at.asc())
        )
    )
    return [node for node in nodes if can_view_node(session, viewer_id, node)]


def get_visible_social_user_ids(session: Session, viewer_id: str) -> list[str]:
    following = get_following_ids(session, viewer_id)
    friends = accepted_friend_ids(session, viewer_id)
    user_ids: list[str] = []
    for candidate in [*following, *friends]:
        if candidate == viewer_id:
            continue
        if candidate in user_ids:
            continue
        if blocked_between(session, viewer_id, candidate):
            continue
        if muted_by(session, viewer_id, candidate):
            continue
        user_ids.append(candidate)
    return user_ids


def accepted_friend_ids(session: Session, user_id: str) -> list[str]:
    rows = session.scalars(
        select(Friendship).where(
            Friendship.status == "accepted",
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        )
    ).all()
    return [row.addressee_id if row.requester_id == user_id else row.requester_id for row in rows]


def follow_user(session: Session, follower_id: str, target_user_id: str) -> SocialRelationshipRead:
    ensure_user_exists(session, follower_id)
    target = ensure_user_exists(session, target_user_id)
    if follower_id == target_user_id:
        raise ValueError("cannot follow yourself")
    if blocked_between(session, follower_id, target_user_id):
        raise ValueError("relationship unavailable")
    existing = session.scalar(
        select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == target_user_id)
    )
    if existing is None:
        session.add(Follow(follower_id=follower_id, following_id=target_user_id))
        follower = ensure_user_exists(session, follower_id)
        follower.following_count += 1
        target.follower_count += 1
        session.add_all([follower, target])
        emit_event(
            session,
            event_type="follow_created",
            aggregate_type="follow",
            aggregate_id=f"{follower_id}:{target_user_id}",
            actor_id=follower_id,
            payload={"target_user_id": target_user_id},
        )
        session.commit()
    return get_relationship(session, follower_id, target_user_id)


def unfollow_user(session: Session, follower_id: str, target_user_id: str) -> SocialRelationshipRead:
    existing = session.scalar(
        select(Follow).where(Follow.follower_id == follower_id, Follow.following_id == target_user_id)
    )
    if existing is not None:
        session.delete(existing)
        follower = ensure_user_exists(session, follower_id)
        target = ensure_user_exists(session, target_user_id)
        follower.following_count = max(0, follower.following_count - 1)
        target.follower_count = max(0, target.follower_count - 1)
        session.add_all([follower, target])
        session.commit()
    return get_relationship(session, follower_id, target_user_id)


def request_friendship(session: Session, requester_id: str, target_user_id: str) -> SocialRelationshipRead:
    ensure_user_exists(session, requester_id)
    ensure_user_exists(session, target_user_id)
    if requester_id == target_user_id:
        raise ValueError("cannot friend yourself")
    if blocked_between(session, requester_id, target_user_id):
        raise ValueError("relationship unavailable")
    record = get_friendship_record(session, requester_id, target_user_id)
    event_type: str | None = None
    event_payload: dict | None = None
    if record is None:
        record = Friendship(requester_id=requester_id, addressee_id=target_user_id, status="pending")
        session.add(record)
        event_type = "friendship_requested"
        event_payload = {"target_user_id": target_user_id}
    elif record.status == "pending" and record.addressee_id == requester_id:
        record.status = "accepted"
        event_type = "friendship_accepted"
        event_payload = {"requester_id": target_user_id}
    elif record.status != "accepted":
        record.requester_id = requester_id
        record.addressee_id = target_user_id
        record.status = "pending"
        event_type = "friendship_requested"
        event_payload = {"target_user_id": target_user_id}
    session.flush()
    if event_type and event_payload is not None:
        emit_event(
            session,
            event_type=event_type,
            aggregate_type="friendship",
            aggregate_id=record.id,
            actor_id=requester_id,
            payload=event_payload,
        )
        session.commit()
    return get_relationship(session, requester_id, target_user_id)


def respond_friendship(session: Session, current_user_id: str, requester_id: str, accept: bool) -> SocialRelationshipRead:
    record = get_friendship_record(session, current_user_id, requester_id)
    if record is None or record.addressee_id != current_user_id or record.status != "pending":
        raise ValueError("friend request not found")
    record.status = "accepted" if accept else "declined"
    emit_event(
        session,
        event_type="friendship_accepted" if accept else "friendship_declined",
        aggregate_type="friendship",
        aggregate_id=record.id,
        actor_id=current_user_id,
        payload={"requester_id": requester_id},
    )
    session.commit()
    return get_relationship(session, current_user_id, requester_id)


def remove_friendship(session: Session, current_user_id: str, target_user_id: str) -> SocialRelationshipRead:
    record = get_friendship_record(session, current_user_id, target_user_id)
    if record is not None:
        session.delete(record)
        session.commit()
    return get_relationship(session, current_user_id, target_user_id)


def set_restriction(session: Session, source_user_id: str, target_user_id: str, kind: str, active: bool) -> SocialRelationshipRead:
    ensure_user_exists(session, source_user_id)
    ensure_user_exists(session, target_user_id)
    if source_user_id == target_user_id:
        raise ValueError("cannot restrict yourself")
    existing = session.scalar(
        select(UserRestriction).where(
            UserRestriction.source_user_id == source_user_id,
            UserRestriction.target_user_id == target_user_id,
            UserRestriction.kind == kind,
        )
    )
    if active:
        if existing is None:
            existing = UserRestriction(source_user_id=source_user_id, target_user_id=target_user_id, kind=kind)
            session.add(existing)
        if kind == "blocked":
            _drop_social_links_between(session, source_user_id, target_user_id)
    elif existing is not None:
        session.delete(existing)
    emit_event(
        session,
        event_type="relationship_restricted",
        aggregate_type="user_restriction",
        aggregate_id=f"{source_user_id}:{target_user_id}:{kind}",
        actor_id=source_user_id,
        payload={"target_user_id": target_user_id, "kind": kind, "active": active},
    )
    session.commit()
    return get_relationship(session, source_user_id, target_user_id)


def get_profile(session: Session, viewer_id: str, target_user_id: str) -> SocialProfileRead:
    user = ensure_user_exists(session, target_user_id)
    relationship = get_relationship(session, viewer_id, target_user_id)
    if relationship.blocked or relationship.blocked_by_target:
        raise ValueError("user not found")

    full = can_view_profile(session, viewer_id, target_user_id)
    visible_nodes = visible_nodes_for_owner(session, viewer_id, target_user_id, include_muted=True)
    top_clusters = _top_clusters_for_visible_nodes(session, visible_nodes)
    return SocialProfileRead(
        id=user.id,
        display_name=user.display_name,
        bio=user.bio if full or viewer_id == target_user_id else "",
        is_public=user.is_public,
        node_count=len(visible_nodes),
        cluster_count=len({node.cluster_id for node in visible_nodes if node.cluster_id}),
        top_clusters=top_clusters,
        created_at=user.created_at if full or viewer_id == target_user_id else None,
        relationship=relationship,
    )


def search_users(session: Session, viewer_id: str, query: str) -> list[UserSearchResult]:
    normalized = query.strip().lower()
    users = list(session.scalars(select(User).order_by(User.follower_count.desc(), User.display_name.asc())))
    results: list[UserSearchResult] = []
    for user in users:
        if user.id == viewer_id:
            continue
        if normalized and normalized not in user.display_name.lower() and normalized not in user.bio.lower():
            continue
        if blocked_between(session, viewer_id, user.id):
            continue
        if not user.is_public and not are_friends(session, viewer_id, user.id):
            continue
        results.append(
            UserSearchResult(
                id=user.id,
                display_name=user.display_name,
                bio=user.bio if can_view_profile(session, viewer_id, user.id) else "",
                is_public=user.is_public,
                top_clusters=_top_clusters_for_visible_nodes(session, visible_nodes_for_owner(session, viewer_id, user.id, include_muted=True)),
                relationship=get_relationship(session, viewer_id, user.id).model_dump(),
            )
        )
        if len(results) >= 20:
            break
    return results


def list_friendships(session: Session, viewer_id: str) -> FriendshipListsRead:
    rows = session.scalars(
        select(Friendship).where(
            or_(Friendship.requester_id == viewer_id, Friendship.addressee_id == viewer_id)
        )
    ).all()
    friends: list[FriendshipListItem] = []
    incoming: list[FriendshipListItem] = []
    outgoing: list[FriendshipListItem] = []
    for row in rows:
        other_id = row.addressee_id if row.requester_id == viewer_id else row.requester_id
        other = ensure_user_exists(session, other_id)
        item = FriendshipListItem(
            id=other.id,
            display_name=other.display_name,
            bio=other.bio if can_view_profile(session, viewer_id, other.id) else "",
            top_clusters=_top_clusters_for_visible_nodes(session, visible_nodes_for_owner(session, viewer_id, other.id, include_muted=True)),
            friendship_state=friendship_state_for(session, viewer_id, other.id),
            relationship=get_relationship(session, viewer_id, other.id),
            updated_at=row.updated_at,
        )
        if row.status == "accepted":
            friends.append(item)
        elif row.status == "pending":
            if row.addressee_id == viewer_id:
                incoming.append(item)
            else:
                outgoing.append(item)
    return FriendshipListsRead(
        friends=friends,
        incoming=incoming,
        outgoing=outgoing,
        suggestions=suggest_users(session, viewer_id),
    )


def suggest_users(session: Session, viewer_id: str, limit: int = 8) -> list[FriendshipListItem]:
    own_nodes = visible_nodes_for_owner(session, viewer_id, viewer_id, include_muted=True)
    own_topics = Counter(topic for node in own_nodes for topic in node.topics)
    results: list[tuple[int, User]] = []
    for user in session.scalars(select(User).where(User.id != viewer_id, User.is_public.is_(True))):
        if blocked_between(session, viewer_id, user.id):
            continue
        relationship = get_relationship(session, viewer_id, user.id)
        if relationship.friendship_state in {"accepted", "incoming", "outgoing"}:
            continue
        visible = visible_nodes_for_owner(session, viewer_id, user.id, include_muted=True)
        if not visible:
            continue
        overlap = sum(1 for topic in {topic for node in visible for topic in node.topics} if own_topics.get(topic))
        if overlap <= 0 and user.follower_count <= 0:
            continue
        results.append((overlap + min(user.follower_count, 5), user))
    results.sort(key=lambda item: item[0], reverse=True)
    suggestions: list[FriendshipListItem] = []
    for _, user in results[:limit]:
        suggestions.append(
            FriendshipListItem(
                id=user.id,
                display_name=user.display_name,
                bio=user.bio,
                top_clusters=_top_clusters_for_visible_nodes(session, visible_nodes_for_owner(session, viewer_id, user.id, include_muted=True)),
                friendship_state="suggested",
                relationship=get_relationship(session, viewer_id, user.id),
                updated_at=user.updated_at,
            )
        )
    return suggestions


def social_neighborhood(session: Session, viewer_id: str) -> SocialNeighborhoodResponse:
    own_nodes = visible_nodes_for_owner(session, viewer_id, viewer_id, include_muted=True)
    own_clusters = {node.cluster_id for node in own_nodes if node.cluster_id}
    own_topics = {topic for node in own_nodes for topic in node.topics}
    items: list[SocialNeighborhoodItem] = []
    for user_id in get_visible_social_user_ids(session, viewer_id):
        visible = visible_nodes_for_owner(session, viewer_id, user_id)
        if not visible:
            continue
        cluster_labels = _top_clusters_for_visible_nodes(session, [node for node in visible if node.cluster_id in own_clusters])
        shared_topics = sorted(own_topics.intersection({topic for node in visible for topic in node.topics}))[:3]
        user = ensure_user_exists(session, user_id)
        items.append(
            SocialNeighborhoodItem(
                user_id=user.id,
                display_name=user.display_name,
                relationship=get_relationship(session, viewer_id, user.id),
                shared_cluster_labels=cluster_labels,
                shared_topics=shared_topics,
                visible_node_count=len(visible),
            )
        )
    return SocialNeighborhoodResponse(items=items)


def _drop_social_links_between(session: Session, a: str, b: str) -> None:
    session.execute(
        delete(Follow).where(
            or_(
                (Follow.follower_id == a) & (Follow.following_id == b),
                (Follow.follower_id == b) & (Follow.following_id == a),
            )
        )
    )
    record = get_friendship_record(session, a, b)
    if record is not None:
        session.delete(record)


def _top_clusters_for_visible_nodes(session: Session, nodes: list[ContentNode]) -> list[str]:
    cluster_ids = [node.cluster_id for node in nodes if node.cluster_id]
    if not cluster_ids:
        return []
    counts = Counter(cluster_ids)
    labels = {
        cluster.id: cluster.label
        for cluster in session.scalars(select(NodeCluster).where(NodeCluster.id.in_(cluster_ids)))
    }
    return [labels[cluster_id] for cluster_id, _ in counts.most_common(3) if cluster_id in labels]
