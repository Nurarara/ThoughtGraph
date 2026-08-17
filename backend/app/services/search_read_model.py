from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.content_node import ContentNode
from app.models.infra_read_models import SearchIndexDocument
from app.models.thought import Thought
from app.schemas.infra import SearchExplainScore, SearchRebuildResponse, SearchResponse, SearchResultItem
from app.services.infra_schema import ensure_infra_schema
from app.services.text_analysis import cosine_similarity, embed_text, summarize_preview, tokenize


SEARCH_INDEX_VERSION = 1


def rebuild_search_index(session: Session, *, user_id: str | None = None) -> SearchRebuildResponse:
    ensure_infra_schema(session)
    delete_statement = delete(SearchIndexDocument)
    if user_id:
        delete_statement = delete_statement.where(SearchIndexDocument.user_id == user_id)
    deleted = session.execute(delete_statement).rowcount or 0

    documents = _content_node_documents(session, user_id) + _thought_documents(session, user_id)
    for document in documents:
        session.add(document)
    session.flush()
    return SearchRebuildResponse(
        indexed=len(documents),
        deleted=deleted,
        source_tables=["content_nodes", "thoughts"],
        user_id=user_id,
    )


def hybrid_search(
    session: Session,
    *,
    user_id: str,
    query: str,
    query_embedding: list[float] | None = None,
    limit: int = 10,
) -> SearchResponse:
    ensure_infra_schema(session)
    terms = [term for term in tokenize(query) if term]
    if not terms:
        return SearchResponse(query=query, items=[], explanation_summary="empty query")

    semantic_vector = query_embedding if query_embedding is not None else embed_text(query)
    docs = list(
        session.scalars(
            select(SearchIndexDocument)
            .where(SearchIndexDocument.user_id == user_id)
            .order_by(SearchIndexDocument.indexed_at.desc())
        )
    )

    scored: list[SearchResultItem] = []
    for doc in docs:
        lexical, matched_terms = _lexical_score(doc.lexeme_text, terms)
        semantic = cosine_similarity(semantic_vector, doc.embedding) if doc.embedding else 0.0
        total = round((0.62 * lexical) + (0.38 * semantic), 5)
        if total <= 0:
            continue
        scored.append(
            SearchResultItem(
                document_id=doc.id,
                source_table=doc.source_table,
                source_id=doc.source_id,
                title=doc.title,
                preview_text=doc.preview_text,
                topics=doc.topics or [],
                score=SearchExplainScore(
                    lexical=round(lexical, 5),
                    semantic=round(semantic, 5),
                    total=total,
                    matched_terms=matched_terms,
                    semantic_available=bool(doc.embedding),
                ),
                explanation={
                    "hybrid_formula": "0.62 * lexical + 0.38 * semantic",
                    "source": "postgres-derived-search-index",
                    "source_updated_at": doc.source_updated_at.isoformat() if doc.source_updated_at else None,
                },
            )
        )

    scored.sort(key=lambda item: item.score.total, reverse=True)
    return SearchResponse(
        query=query,
        items=scored[:limit],
        explanation_summary="results are ranked from a rebuildable Postgres-derived search index using lexical matches and embedding similarity",
    )


def _content_node_documents(session: Session, user_id: str | None) -> list[SearchIndexDocument]:
    statement = select(ContentNode)
    if user_id:
        statement = statement.where(ContentNode.user_id == user_id)
    docs = []
    for node in session.scalars(statement):
        body = node.content_text or node.preview_text or ""
        title = node.title
        lexeme = _lexeme_text(title, body, node.topics)
        docs.append(
            SearchIndexDocument(
                source_table="content_nodes",
                source_id=node.id,
                user_id=node.user_id,
                title=title,
                body=body,
                preview_text=node.preview_text or summarize_preview(body),
                topics=node.topics or [],
                embedding=node.embedding or embed_text(" ".join([title or "", body])),
                lexeme_text=lexeme,
                source_updated_at=node.updated_at,
                indexed_at=datetime.now(timezone.utc),
                index_version=SEARCH_INDEX_VERSION,
                explanation={"canonical_table": "content_nodes", "canonical_id": node.id},
            )
        )
    return docs


def _thought_documents(session: Session, user_id: str | None) -> list[SearchIndexDocument]:
    statement = select(Thought)
    if user_id:
        statement = statement.where(Thought.user_id == user_id)
    docs = []
    for thought in session.scalars(statement):
        title = summarize_preview(thought.content, limit=80)
        lexeme = _lexeme_text(title, thought.content, thought.topics)
        docs.append(
            SearchIndexDocument(
                source_table="thoughts",
                source_id=thought.id,
                user_id=thought.user_id,
                title=title,
                body=thought.content,
                preview_text=summarize_preview(thought.content),
                topics=thought.topics or [],
                embedding=thought.vector or embed_text(thought.content),
                lexeme_text=lexeme,
                source_updated_at=thought.updated_at,
                indexed_at=datetime.now(timezone.utc),
                index_version=SEARCH_INDEX_VERSION,
                explanation={"canonical_table": "thoughts", "canonical_id": thought.id},
            )
        )
    return docs


def _lexeme_text(title: str | None, body: str, topics: list[str]) -> str:
    return " ".join(part for part in [title or "", body, " ".join(topics or [])] if part).lower()


def _lexical_score(lexeme_text: str, terms: list[str]) -> tuple[float, list[str]]:
    counts = Counter(re.findall(r"[a-zA-Z']+", lexeme_text.lower()))
    matched = [term for term in terms if counts.get(term, 0) > 0 or term in lexeme_text]
    if not matched:
        return 0.0, []
    raw = sum(counts.get(term, 0) for term in matched)
    return min(1.0, raw / max(len(terms), 1)), matched
