from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from math import isfinite
from statistics import fmean

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.content_node import ContentNode
from app.models.discovery_materialization import DiscoveryMaterialization
from app.models.media_asset import MediaAsset
from app.models.node_cluster import NodeCluster
from app.models.trust_moderation import TrustClaim
from app.models.user import User
from app.schemas.discovery import (
    AdjacentPeopleResponse,
    DiscoveryExplanationRead,
    DiscoveryExploreResponse,
    DiscoveryFilterAvailability,
    DiscoveryFilters,
    DiscoveryNodeItemRead,
    DiscoveryPersonItemRead,
    DiscoveryScoreBreakdown,
    RelatedIdeasResponse,
)
from app.schemas.graph import GraphNodeRead
from app.schemas.social import SocialRelationshipRead
from app.services.event_service import emit_event
from app.services.media_service import to_media_asset_read
from app.services.social_service import (
    blocked_between,
    can_view_node,
    get_relationship,
    get_visible_social_user_ids,
    visible_nodes_for_owner,
)
from app.services.text_analysis import cosine_similarity, embed_text
from app.services.trust_moderation_service import is_blocked_from_discovery
from app.services.user_service import ensure_user_exists


def explore_discovery(session: Session, user_id: str, filters: DiscoveryFilters) -> DiscoveryExploreResponse:
    ensure_user_exists(session, user_id)
    own_nodes = visible_nodes_for_owner(session, user_id, user_id, include_muted=True)
    candidates = _candidate_nodes(session, user_id, own_nodes)
    interest_embedding = _interest_embedding(own_nodes, filters.q)
    unavailable_filters = _unavailable_filters(filters)
    ranked = _rank_node_candidates(
        session,
        viewer_id=user_id,
        own_nodes=own_nodes,
        candidates=candidates,
        interest_embedding=interest_embedding,
        filters=filters,
        unavailable_filters=unavailable_filters,
    )
    items = ranked[: filters.limit]
    summary = _explore_summary(filters, len(items))
    materialization = _materialize(
        session,
        user_id=user_id,
        mode="explore",
        subject_node_id=None,
        query_text=filters.q,
        filters_json=filters.model_dump(),
        explanation_summary=summary,
        results_json={"items": [item.model_dump(mode="json") for item in items]},
    )
    return DiscoveryExploreResponse(
        materialization_id=materialization.id,
        generated_at=materialization.created_at,
        filters=filters,
        filter_availability=DiscoveryFilterAvailability(
            trusted_only=True,
        ),
        explanation_summary=summary,
        items=items,
    )


def related_ideas(session: Session, user_id: str, node_id: str, limit: int | None = None) -> RelatedIdeasResponse:
    subject = session.get(ContentNode, node_id)
    if subject is None or not can_view_node(session, user_id, subject):
        raise ValueError("node not found")
    own_nodes = visible_nodes_for_owner(session, user_id, user_id, include_muted=True)
    all_candidates = _candidate_nodes(session, user_id, own_nodes)
    candidates = [node for node in all_candidates if node.id != subject.id and can_view_node(session, user_id, node)]
    filters = DiscoveryFilters(limit=limit or min(8, get_settings().discovery_default_limit))
    ranked = _rank_node_candidates(
        session,
        viewer_id=user_id,
        own_nodes=own_nodes,
        candidates=candidates,
        interest_embedding=_node_embedding(subject),
        filters=filters,
        unavailable_filters=[],
        subject=subject,
    )
    items = ranked[: filters.limit]
    summary = f"Related ideas are ranked by semantic overlap, novelty, and explainable social distance from {subject.title or 'the selected node'}."
    materialization = _materialize(
        session,
        user_id=user_id,
        mode="related",
        subject_node_id=subject.id,
        query_text=subject.title or subject.preview_text,
        filters_json={"limit": filters.limit},
        explanation_summary=summary,
        results_json={"items": [item.model_dump(mode="json") for item in items]},
    )
    return RelatedIdeasResponse(
        materialization_id=materialization.id,
        generated_at=materialization.created_at,
        subject=_graph_node_read(session, user_id, subject),
        explanation_summary=summary,
        items=items,
    )


def adjacent_people(session: Session, user_id: str, limit: int | None = None) -> AdjacentPeopleResponse:
    own_nodes = visible_nodes_for_owner(session, user_id, user_id, include_muted=True)
    own_topics = {topic for node in own_nodes for topic in node.topics}
    own_clusters = {node.cluster_id for node in own_nodes if node.cluster_id}
    items: list[DiscoveryPersonItemRead] = []

    candidate_users = []
    seen: set[str] = set()
    for social_user_id in get_visible_social_user_ids(session, user_id):
        if social_user_id not in seen:
            seen.add(social_user_id)
            candidate_users.append(social_user_id)
    public_users = session.scalars(select(User).where(User.is_public.is_(True), User.id != user_id)).all()
    for public_user in public_users:
        if public_user.id in seen or blocked_between(session, user_id, public_user.id):
            continue
        seen.add(public_user.id)
        candidate_users.append(public_user.id)

    for candidate_user_id in candidate_users:
        visible = visible_nodes_for_owner(session, user_id, candidate_user_id)
        if not visible:
            continue
        user = ensure_user_exists(session, candidate_user_id)
        shared_topics = sorted(own_topics.intersection({topic for node in visible for topic in node.topics}))[:4]
        if not shared_topics and not get_relationship(session, user_id, candidate_user_id).following:
            continue
        shared_cluster_labels = _shared_cluster_labels(session, own_clusters, visible)
        relationship = get_relationship(session, user_id, candidate_user_id)
        social_score = _social_proximity_score(relationship)
        relevance = min(1.0, len(shared_topics) / 3) if shared_topics else 0.25
        novelty = 1.0 - min(0.8, social_score * 0.45)
        trust = _trust_score_for_nodes(session, visible)
        diversity = 1.0 if not relationship.following else 0.55
        total = round(
            (relevance * 0.34)
            + (novelty * 0.17)
            + (trust * 0.12)
            + (diversity * 0.17)
            + (social_score * 0.20),
            4,
        )
        breakdown = DiscoveryScoreBreakdown(
            relevance=round(relevance, 4),
            novelty=round(novelty, 4),
            trust=round(trust, 4),
            diversity=round(diversity, 4),
            social_proximity=round(social_score, 4),
            total=total,
        )
        summary = (
            f"{user.display_name} is adjacent to you through shared topics like {', '.join(shared_topics[:2])}."
            if shared_topics
            else f"{user.display_name} is public but still near your graph through explainable topic bridges."
        )
        items.append(
            DiscoveryPersonItemRead(
                user_id=user.id,
                display_name=user.display_name,
                bio=user.bio,
                shared_topics=shared_topics,
                shared_cluster_labels=shared_cluster_labels,
                visible_node_count=len(visible),
                relationship=relationship,
                explanation=DiscoveryExplanationRead(
                    primary_reason="shared_topics" if shared_topics else "public_adjacency",
                    summary=summary,
                    matched_topics=shared_topics,
                    relationship_to_viewer=_relationship_label(relationship),
                    signal_notes=[
                        f"{len(visible)} visible nodes contribute to adjacency",
                        "social proximity remains explainable through follows, friendships, and topic overlap",
                    ],
                    score_breakdown=breakdown,
                ),
            )
        )

    items.sort(key=lambda item: item.explanation.score_breakdown.total, reverse=True)
    final_items = items[: limit or min(8, get_settings().discovery_default_limit)]
    summary = "Adjacent people are ranked by shared topics, visible graph overlap, and transparent social distance."
    materialization = _materialize(
        session,
        user_id=user_id,
        mode="adjacent_people",
        subject_node_id=None,
        query_text=None,
        filters_json={"limit": limit or get_settings().discovery_default_limit},
        explanation_summary=summary,
        results_json={"items": [item.model_dump(mode="json") for item in final_items]},
    )
    return AdjacentPeopleResponse(
        materialization_id=materialization.id,
        generated_at=materialization.created_at,
        explanation_summary=summary,
        items=final_items,
    )


def _candidate_nodes(session: Session, user_id: str, own_nodes: list[ContentNode]) -> list[ContentNode]:
    candidates: dict[str, ContentNode] = {}
    social_user_ids = get_visible_social_user_ids(session, user_id)
    public_users = session.scalars(select(User).where(User.is_public.is_(True), User.id != user_id)).all()
    public_user_ids = [user.id for user in public_users if not blocked_between(session, user_id, user.id)]
    for candidate_user_id in [*social_user_ids, *public_user_ids]:
        for node in visible_nodes_for_owner(session, user_id, candidate_user_id):
            candidates[node.id] = node
    for node in own_nodes:
        candidates.setdefault(node.id, node)
    ordered = sorted(candidates.values(), key=lambda item: item.updated_at, reverse=True)
    return ordered[: get_settings().discovery_candidate_limit]


def _interest_embedding(own_nodes: list[ContentNode], query_text: str | None) -> list[float]:
    if query_text and query_text.strip():
        return _canonical_embedding(embed_text(query_text.strip()), query_text.strip())
    if own_nodes:
        embeddings = [_node_embedding(node) for node in own_nodes[-min(10, len(own_nodes)) :]]
        if embeddings:
            return [round(fmean(vector[index] for vector in embeddings), 6) for index in range(len(embeddings[0]))]
    return _canonical_embedding(embed_text("thoughtgraph explore"), "thoughtgraph explore")


def _node_embedding(node: ContentNode) -> list[float]:
    fallback_text = " ".join(
        value for value in (node.title or "", node.content_text or "", node.preview_text or "") if value
    ).strip() or "thoughtgraph node"
    return _canonical_embedding(node.embedding, fallback_text)


def _canonical_embedding(value: object, fallback_text: str) -> list[float]:
    dimensions = get_settings().vector_dimensions
    if isinstance(value, list) and len(value) == dimensions:
        try:
            normalized = [float(item) for item in value]
        except (TypeError, ValueError):
            normalized = []
        if normalized and all(isfinite(item) for item in normalized):
            return normalized

    fallback = [float(item) for item in embed_text(fallback_text)]
    if len(fallback) >= dimensions:
        return fallback[:dimensions]
    return fallback + [0.0] * (dimensions - len(fallback))


def _rank_node_candidates(
    session: Session,
    *,
    viewer_id: str,
    own_nodes: list[ContentNode],
    candidates: list[ContentNode],
    interest_embedding: list[float],
    filters: DiscoveryFilters,
    unavailable_filters: list[str],
    subject: ContentNode | None = None,
) -> list[DiscoveryNodeItemRead]:
    own_topics = {topic for node in own_nodes for topic in node.topics}
    own_cluster_counts = Counter(node.cluster_id for node in own_nodes if node.cluster_id)
    selected_cluster_counts: Counter[str] = Counter()
    selected_author_counts: Counter[str] = Counter()
    ranked_raw: list[tuple[float, ContentNode, DiscoveryExplanationRead]] = []

    for candidate in candidates:
        if subject and candidate.id == subject.id:
            continue
        if not _media_is_discovery_safe(session, candidate):
            continue
        if is_blocked_from_discovery(session, "node", candidate.id):
            continue
        if is_blocked_from_discovery(session, "user", candidate.user_id):
            continue
        if viewer_id != candidate.user_id and blocked_between(session, viewer_id, candidate.user_id):
            continue

        relationship = get_relationship(session, viewer_id, candidate.user_id)
        social_score = _social_proximity_score(relationship, self_node=candidate.user_id == viewer_id)
        if filters.close_to_me and social_score < 0.45:
            continue
        if filters.outside_my_bubble and social_score > 0.55:
            continue

        relevance = max(0.0, cosine_similarity(interest_embedding, _node_embedding(candidate)))
        matched_topics = sorted(own_topics.intersection(candidate.topics))
        if matched_topics:
            relevance = min(1.0, relevance + 0.08)
        novelty = _novelty_score(candidate)
        trust = _trust_score_for_node(session, candidate)
        if filters.high_evidence and trust < 0.55:
            continue
        if filters.trusted_only and not _is_trusted_node(session, candidate):
            continue
        if filters.new_low_spread and not _new_low_spread(candidate):
            continue
        diversity = _diversity_seed_score(candidate, own_cluster_counts)

        total = round(
            (relevance * 0.38)
            + (novelty * 0.17)
            + (trust * 0.14)
            + (diversity * 0.11)
            + (social_score * 0.20),
            4,
        )
        breakdown = DiscoveryScoreBreakdown(
            relevance=round(relevance, 4),
            novelty=round(novelty, 4),
            trust=round(trust, 4),
            diversity=round(diversity, 4),
            social_proximity=round(social_score, 4),
            total=total,
        )
        primary_reason = _primary_reason(relevance, novelty, social_score, filters, subject)
        notes = _signal_notes(candidate, relationship, subject)
        if filters.trusted_only:
            notes.append("trusted source filter applied using supported or verified trust claims")
        summary = _node_summary(candidate, primary_reason, matched_topics, relationship, subject)
        explanation = DiscoveryExplanationRead(
            primary_reason=primary_reason,
            summary=summary,
            matched_topics=matched_topics,
            relationship_to_viewer=_relationship_label(relationship),
            signal_notes=notes,
            unavailable_filters=unavailable_filters,
            score_breakdown=breakdown,
        )
        ranked_raw.append((total, candidate, explanation))

    items: list[DiscoveryNodeItemRead] = []
    remaining = ranked_raw[:]
    while remaining:
        best_index = 0
        best_adjusted = -1.0
        for index, (_, candidate, explanation) in enumerate(remaining):
            cluster_penalty = 0.08 * selected_cluster_counts.get(candidate.cluster_id or "", 0)
            author_penalty = 0.06 * selected_author_counts.get(candidate.user_id, 0)
            adjusted = round(max(0.0, explanation.score_breakdown.total - cluster_penalty - author_penalty), 4)
            if adjusted > best_adjusted:
                best_index = index
                best_adjusted = adjusted
        _, candidate, explanation = remaining.pop(best_index)
        adjusted_total = best_adjusted
        explanation.score_breakdown.total = adjusted_total
        items.append(
            DiscoveryNodeItemRead(
                node=_graph_node_read(session, viewer_id, candidate),
                explanation=explanation,
            )
        )
        selected_cluster_counts[candidate.cluster_id or ""] += 1
        selected_author_counts[candidate.user_id] += 1
    return items


def _media_is_discovery_safe(session: Session, node: ContentNode) -> bool:
    if not node.media_asset_id:
        return True
    asset = session.get(MediaAsset, node.media_asset_id)
    return asset is not None and asset.moderation_status == "approved"


def _graph_node_read(session: Session, viewer_id: str, node: ContentNode) -> GraphNodeRead:
    cluster = session.get(NodeCluster, node.cluster_id) if node.cluster_id else None
    author = session.get(User, node.user_id)
    media_asset = session.get(MediaAsset, node.media_asset_id) if node.media_asset_id else None
    media_read = to_media_asset_read(media_asset) if media_asset else None
    relationship = get_relationship(session, viewer_id, node.user_id) if viewer_id != node.user_id else None
    return GraphNodeRead(
        id=node.id,
        kind=node.kind,
        title=node.title,
        content_text=node.content_text,
        preview_text=node.preview_text,
        visibility=node.visibility,
        created_at=_ensure_utc(node.created_at),
        updated_at=_ensure_utc(node.updated_at),
        topics=node.topics,
        cluster_id=node.cluster_id,
        cluster_label=cluster.label if cluster else None,
        cluster_color=cluster.color if cluster else None,
        connection_count=node.connection_count,
        x=0.0,
        y=0.0,
        author_id=node.user_id,
        author_display_name=author.display_name if author else None,
        relationship_to_viewer="self" if viewer_id == node.user_id else _relationship_label(relationship),
        is_social=viewer_id != node.user_id,
        media_asset_id=media_asset.id if media_asset else None,
        media_kind=media_asset.kind if media_asset else None,
        media_status=media_asset.status if media_asset else None,
        thumbnail_url=media_read.thumbnail_url if media_read else None,
        playback_url=media_read.playback_url if media_read else None,
        duration_seconds=media_asset.duration_seconds if media_asset else None,
        media_url=media_read.original_url if media_read else None,
        link_url=node.link_url,
        reply_to_node_id=node.reply_to_node_id,
        quote_of_node_id=node.quote_of_node_id,
    )


def _novelty_score(node: ContentNode) -> float:
    age_hours = max((datetime.now(timezone.utc) - _ensure_utc(node.created_at)).total_seconds() / 3600, 1)
    recency_score = max(0.2, 1.0 - min(age_hours / 168, 0.7))
    spread_penalty = min(node.connection_count / 12, 0.45)
    return round(max(0.0, recency_score + 0.25 - spread_penalty), 4)


def _new_low_spread(node: ContentNode) -> bool:
    age_hours = max((datetime.now(timezone.utc) - _ensure_utc(node.created_at)).total_seconds() / 3600, 1)
    return age_hours <= 168 and node.connection_count <= 3


def _trust_proxy_for_node(node: ContentNode) -> float:
    if node.link_url:
        return 0.82
    if node.quote_of_node_id:
        return 0.68
    if node.kind in {"image", "video"}:
        return 0.6
    if node.reply_to_node_id:
        return 0.52
    return 0.34


def _trust_score_for_node(session: Session, node: ContentNode) -> float:
    trusted_claim_score = session.scalar(
        select(func.max(TrustClaim.confidence_score)).where(
            TrustClaim.node_id == node.id,
            TrustClaim.verification_status.in_(("supported", "verified")),
        )
    )
    if trusted_claim_score is not None:
        return round(max(0.72, float(trusted_claim_score)), 4)
    negative_claim_score = session.scalar(
        select(func.max(TrustClaim.confidence_score)).where(
            TrustClaim.node_id == node.id,
            TrustClaim.verification_status.in_(("disputed", "refuted")),
        )
    )
    if negative_claim_score is not None:
        return round(min(_trust_proxy_for_node(node), max(0.0, 1.0 - float(negative_claim_score))), 4)
    return _trust_proxy_for_node(node)


def _is_trusted_node(session: Session, node: ContentNode) -> bool:
    return (
        session.scalar(
            select(TrustClaim.id)
            .where(
                TrustClaim.node_id == node.id,
                TrustClaim.verification_status.in_(("supported", "verified")),
                TrustClaim.confidence_score >= 0.55,
            )
            .limit(1)
        )
        is not None
    )


def _trust_score_for_nodes(session: Session, nodes: list[ContentNode]) -> float:
    if not nodes:
        return 0.0
    return round(fmean(_trust_score_for_node(session, node) for node in nodes[: min(8, len(nodes))]), 4)


def _diversity_seed_score(node: ContentNode, own_cluster_counts: Counter[str]) -> float:
    if not node.cluster_id:
        return 0.75
    cluster_weight = own_cluster_counts.get(node.cluster_id, 0)
    if cluster_weight == 0:
        return 1.0
    return round(max(0.25, 0.9 - min(cluster_weight / 8, 0.55)), 4)


def _social_proximity_score(relationship: SocialRelationshipRead, self_node: bool = False) -> float:
    if self_node:
        return 1.0
    if relationship.friendship_state == "accepted":
        return 0.92
    if relationship.following and relationship.followed_by:
        return 0.8
    if relationship.following:
        return 0.66
    if relationship.followed_by:
        return 0.58
    return 0.22


def _primary_reason(
    relevance: float,
    novelty: float,
    social_score: float,
    filters: DiscoveryFilters,
    subject: ContentNode | None,
) -> str:
    if subject is not None:
        return "semantic_overlap"
    if filters.outside_my_bubble and social_score <= 0.3:
        return "outside_bubble"
    if filters.close_to_me and social_score >= 0.6:
        return "social_proximity"
    if novelty >= relevance and novelty >= social_score:
        return "novelty"
    if social_score >= relevance:
        return "social_proximity"
    return "semantic_overlap"


def _signal_notes(candidate: ContentNode, relationship: SocialRelationshipRead, subject: ContentNode | None) -> list[str]:
    notes = []
    if candidate.topics:
        notes.append(f"topics: {', '.join(candidate.topics[:3])}")
    if relationship.friendship_state == "accepted":
        notes.append("comes from a friend in your social graph")
    elif relationship.following:
        notes.append("comes from someone you already follow")
    elif candidate.visibility == "public":
        notes.append("public node available beyond your current bubble")
    if candidate.link_url:
        notes.append("includes a linked reference, which lifts the current evidence proxy")
    elif candidate.quote_of_node_id:
        notes.append("quotes another node, which adds inspectable context before the trust layer exists")
    if subject is not None:
        notes.append("ranked relative to the node you selected")
    return notes


def _node_summary(
    candidate: ContentNode,
    primary_reason: str,
    matched_topics: list[str],
    relationship: SocialRelationshipRead,
    subject: ContentNode | None,
) -> str:
    title = candidate.title or candidate.preview_text[:40] or "This node"
    if primary_reason == "social_proximity":
        return f"{title} is close to you socially and still overlaps with your visible graph."
    if primary_reason == "outside_bubble":
        return f"{title} is intentionally outside your close graph but still connects through explainable topic overlap."
    if primary_reason == "novelty":
        return f"{title} is fresh and low-spread, so it expands your graph before it hardens into the usual cluster."
    if matched_topics:
        return f"{title} overlaps with your graph through {', '.join(matched_topics[:2])}."
    if subject is not None:
        return f"{title} stays near the selected node through semantic similarity and context."
    if relationship.following or relationship.friendship_state == "accepted":
        return f"{title} comes from someone near your social graph and is still explainable through visible context."
    return f"{title} connects to your graph through semantic overlap without relying on opaque engagement ranking."


def _shared_cluster_labels(session: Session, own_clusters: set[str], visible_nodes: list[ContentNode]) -> list[str]:
    shared_ids = {node.cluster_id for node in visible_nodes if node.cluster_id and node.cluster_id in own_clusters}
    if not shared_ids:
        return []
    clusters = session.scalars(select(NodeCluster).where(NodeCluster.id.in_(shared_ids))).all()
    return [cluster.label for cluster in clusters[:3]]


def _relationship_label(relationship: SocialRelationshipRead | None) -> str | None:
    if relationship is None:
        return None
    if relationship.friendship_state == "accepted":
        return "friend"
    if relationship.following and relationship.followed_by:
        return "mutual"
    if relationship.following:
        return "following"
    if relationship.followed_by:
        return "followed_by"
    return "public"


def _unavailable_filters(filters: DiscoveryFilters) -> list[str]:
    return []


def _explore_summary(filters: DiscoveryFilters, result_count: int) -> str:
    parts = ["Explore ideas are ranked by relevance, novelty, social proximity, diversity, and a pre-trust evidence proxy."]
    if filters.close_to_me:
        parts.append("Results were constrained toward your near social graph.")
    if filters.outside_my_bubble:
        parts.append("Results were pushed away from your immediate bubble.")
    if filters.new_low_spread:
        parts.append("Results favor newer, lower-spread nodes.")
    if filters.q:
        parts.append(f'Query: "{filters.q}".')
    parts.append(f"{result_count} explainable suggestions were materialized.")
    return " ".join(parts)


def _materialize(
    session: Session,
    *,
    user_id: str,
    mode: str,
    subject_node_id: str | None,
    query_text: str | None,
    filters_json: dict,
    explanation_summary: str,
    results_json: dict,
) -> DiscoveryMaterialization:
    materialization = DiscoveryMaterialization(
        user_id=user_id,
        mode=mode,
        subject_node_id=subject_node_id,
        query_text=query_text,
        filters_json=filters_json,
        result_count=len(results_json.get("items", [])),
        explanation_summary=explanation_summary,
        results_json=results_json,
    )
    session.add(materialization)
    session.flush()
    emit_event(
        session,
        event_type="recommendation_materialized",
        aggregate_type="discovery_materialization",
        aggregate_id=materialization.id,
        actor_id=user_id,
        payload={
            "mode": mode,
            "result_count": materialization.result_count,
            "subject_node_id": subject_node_id,
        },
    )
    session.commit()
    session.refresh(materialization)
    return materialization


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
