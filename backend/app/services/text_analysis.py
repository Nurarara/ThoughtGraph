from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from math import log10
import re

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer


STOPWORDS = {
    "about",
    "after",
    "again",
    "being",
    "could",
    "every",
    "from",
    "have",
    "just",
    "like",
    "really",
    "still",
    "their",
    "there",
    "these",
    "thing",
    "think",
    "this",
    "what",
    "when",
    "with",
    "would",
    "your",
    "into",
    "than",
    "them",
    "then",
    "that",
    "been",
    "also",
    "want",
    "need",
    "make",
    "made",
    "more",
    "less",
}

EMOTION_KEYWORDS = {
    "joy": {"grateful", "excited", "joy", "happy", "optimistic", "hopeful", "proud", "energized"},
    "sadness": {"sad", "tired", "exhausted", "lonely", "down", "empty", "hurt", "grief"},
    "fear": {"anxious", "worry", "worried", "panic", "afraid", "uncertain", "nervous", "stress"},
    "anger": {"angry", "frustrated", "resent", "resentful", "annoyed", "furious", "irritated"},
    "growth": {"learning", "build", "shipping", "improve", "improving", "progress", "discipline", "focus"},
}

TOPIC_SYNONYMS = {
    "career": {"job", "career", "work", "promotion", "manager", "company", "interview", "salary"},
    "relationships": {"friend", "partner", "family", "relationship", "dating", "marriage", "love"},
    "health": {"health", "sleep", "fitness", "diet", "gym", "energy", "doctor", "body"},
    "politics": {"politics", "election", "policy", "government", "democracy", "ideology"},
    "ai": {"ai", "model", "llm", "agent", "embedding", "openai", "anthropic", "nvidia"},
    "money": {"money", "finance", "invest", "investing", "budget", "debt", "wealth"},
    "creativity": {"write", "writing", "art", "music", "design", "create", "creative"},
}

vectorizer = HashingVectorizer(
    n_features=256,
    alternate_sign=False,
    norm="l2",
    ngram_range=(1, 2),
)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def embed_text(text: str) -> list[float]:
    return vectorizer.transform([text]).toarray()[0].astype(float).tolist()


def infer_topics(text: str) -> list[str]:
    tokens = tokenize(text)
    matched = []
    token_set = set(tokens)
    for label, synonyms in TOPIC_SYNONYMS.items():
        if token_set.intersection(synonyms):
            matched.append(label)

    if matched:
        return matched[:3]

    counts = Counter(token for token in tokens if len(token) > 3 and token not in STOPWORDS)
    return [token for token, _ in counts.most_common(3)] or ["general"]


def infer_emotion(text: str) -> str:
    tokens = tokenize(text)
    counts = {emotion: sum(token in keywords for token in tokens) for emotion, keywords in EMOTION_KEYWORDS.items()}
    if not any(counts.values()):
        if "!" in text and len(tokens) > 6:
            return "joy"
        return "neutral"
    return max(counts, key=counts.get)


def calculate_activity_score(created_at: datetime, connection_count: int) -> int:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    age_hours = max((now - created_at).total_seconds() / 3600, 1)
    recency_score = max(1, 6 - int(log10(age_hours + 1) * 2))
    return max(1, recency_score + connection_count)


def summarize_preview(content: str, limit: int = 120) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_array = np.array(a)
    b_array = np.array(b)
    denom = np.linalg.norm(a_array) * np.linalg.norm(b_array)
    if denom == 0:
        return 0.0
    return float(np.dot(a_array, b_array) / denom)
