"""Deterministic, explainable ticket clustering - no ML model, no LLM.

Pipeline:
  1. Preprocess each ticket's subject + resolution text (lowercase, strip
     punctuation, collapse whitespace - see text_preprocessing.py).
  2. Tag each ticket with 0+ curated support-domain categories (auth,
     billing, api, data, email - see domain_categories.py) via plain
     substring matching against a fixed keyword list. The matched tags are
     woven back into the ticket's clustering text as extra repeated tokens.
     This gives two tickets in the same support domain a shared vocabulary
     token even when their literal wording is completely different (e.g.
     "card declined" and "duplicate invoice charge" both surface a
     "cattag_billing" token) - it is still ordinary keyword matching, just
     applied before vectorization rather than after.
  3. TF-IDF vectorize (unigrams + bigrams) over: subject (2x, it names the
     issue) + resolution (1x, supporting context) + category tags (3x, a
     deliberately strong bridging signal - see TAG_REPEAT below).
  4. Cluster via cosine-distance agglomerative clustering with *average*
     linkage and a fixed distance threshold - not a chosen k. Two tickets
     only end up together once the algorithm's average pairwise similarity
     between their clusters clears the threshold; nothing here picks "3 to
     5 clusters" up front the way the previous KMeans(k=3..5) approach did.
  5. If more clusters survive than MAX_CLUSTERS, the same linkage tree is
     cut one level lower (n_clusters=MAX_CLUSTERS) rather than restarting
     with a different method - still driven by the same similarity
     ordering, just capping how many theme cards the UI has to show.

Thresholds were tuned against data/sample_tickets.csv (20 tickets, 5 true
4-ticket themes) and reproduce that grouping exactly; see docs/03-architecture.md
for the reasoning and the tuning notes.
"""

from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .domain_categories import TAG_PREFIX, Category, tag_categories
from .text_preprocessing import COMBINED_STOP_WORDS, preprocess_text

# Average-linkage cosine DISTANCE at which merging stops (distance = 1 -
# cosine_similarity). 0.95 means "keep merging clusters whose average
# pairwise similarity is >= 0.05". Loose in absolute terms because raw
# TF-IDF similarity between two short, differently-worded tickets is
# naturally low even when they describe the same recurring issue; the
# category-tag bridging in step 2 is what makes a 0.05 bar meaningful
# rather than noise.
DISTANCE_THRESHOLD = 0.95

# Hard cap on how many theme cards the UI ever has to render, even if the
# threshold above leaves more clusters than that.
MAX_CLUSTERS = 6

# Below this many tickets there isn't enough data for a meaningful theme
# split; the caller (csv_ingest) already enforces a higher minimum, this is
# just the point below which clustering degenerates to "everything is one
# cluster."
MIN_TICKETS_TO_SPLIT = 2

# How many times matched category tags are repeated in a ticket's
# clustering text. Higher repetition = higher term frequency = a shared
# domain tag counts for more than one incidental word overlap. Tuned
# empirically: 3x was the smallest repetition that reliably reunited
# same-domain tickets (e.g. all 4 billing tickets) without merging
# unrelated ones.
TAG_REPEAT = 3

TOP_TERMS_PER_CLUSTER = 8


class ClusteringError(ValueError):
    pass


def _clustering_text(ticket: Dict[str, Any], categories: Optional[Dict[str, Category]] = None) -> str:
    subject = preprocess_text(ticket["subject"])
    description = preprocess_text(ticket.get("description", ""))
    resolution = preprocess_text(ticket["resolution"])

    tags = tag_categories(f"{subject} {description} {resolution}", categories)
    tag_tokens = " ".join(f"{TAG_PREFIX}{t}" for t in tags)
    tag_text = f"{tag_tokens} " * TAG_REPEAT if tags else ""

    # Title weighted 2x (it names the issue), resolution 1x (supporting
    # context), tags repeated TAG_REPEAT times (bridging signal). The raw
    # description is intentionally NOT included here - it's free-form
    # customer wording that would dilute the title/resolution signal; it's
    # only used above to help pick category tags.
    return f"{subject} {subject} {resolution} {tag_text}".strip()


def _top_terms(centroid: np.ndarray, feature_names: np.ndarray, limit: int) -> List[str]:
    """Top TF-IDF terms for a cluster centroid, excluding synthetic category tags."""
    order = centroid.argsort()[::-1]
    terms: List[str] = []
    for idx in order:
        if centroid[idx] <= 0:
            break
        term = feature_names[idx]
        if term.startswith(TAG_PREFIX):
            continue
        terms.append(term)
        if len(terms) >= limit:
            break
    return terms


def _average_internal_similarity(sim: np.ndarray, indices: List[int]) -> float:
    if len(indices) <= 1:
        return 1.0
    pairs = [
        sim[i, j]
        for a, i in enumerate(indices)
        for j in indices[a + 1 :]
    ]
    return float(np.mean(pairs))


def cluster_tickets(
    tickets: List[Dict[str, Any]], categories: Optional[Dict[str, Category]] = None
) -> List[Dict[str, Any]]:
    """Group tickets into recurring-issue themes via TF-IDF + cosine similarity.

    Each input ticket dict needs: subject, resolution, external_id, and
    optionally description. Returns a list of cluster dicts:
      {ticket_indices, ticket_ids, ticket_count, keywords, avg_similarity,
       member_similarity}
    `ticket_indices` are positions into the input `tickets` list, so callers
    can map clusters back to their own identifiers.

    `categories` defaults to the static curated CATEGORIES (domain_categories.py);
    pass a dict from `domain_categories.merged_categories` to also apply the
    tag-bridging boost for user-approved custom categories.
    """
    n = len(tickets)
    if n == 0:
        raise ClusteringError("No tickets to cluster.")

    corpus = [_clustering_text(t, categories) for t in tickets]
    vectorizer = TfidfVectorizer(
        stop_words=list(COMBINED_STOP_WORDS),
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.9,
    )
    matrix = vectorizer.fit_transform(corpus)
    dense = matrix.toarray()
    feature_names = vectorizer.get_feature_names_out()
    sim = cosine_similarity(dense)

    if n < MIN_TICKETS_TO_SPLIT + 1:
        labels = np.zeros(n, dtype=int)
    else:
        model = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=DISTANCE_THRESHOLD,
            metric="cosine",
            linkage="average",
        )
        labels = model.fit_predict(dense)

        if len(set(labels)) > MAX_CLUSTERS:
            # Cut the same average-linkage tree one level lower instead of
            # switching methods - still ordered by similarity, just capped.
            model = AgglomerativeClustering(
                n_clusters=MAX_CLUSTERS, metric="cosine", linkage="average"
            )
            labels = model.fit_predict(dense)

    clusters: List[Dict[str, Any]] = []
    for label in sorted(set(labels)):
        indices = [i for i, l in enumerate(labels) if l == label]
        centroid = dense[indices].mean(axis=0)
        member_similarity = {
            tickets[i]["external_id"]: float(cosine_similarity([dense[i]], [centroid])[0, 0])
            for i in indices
        }
        clusters.append(
            {
                "ticket_indices": indices,
                "ticket_ids": [tickets[i]["external_id"] for i in indices],
                "ticket_count": len(indices),
                "keywords": _top_terms(centroid, feature_names, TOP_TERMS_PER_CLUSTER),
                "avg_similarity": _average_internal_similarity(sim, indices),
                "member_similarity": member_similarity,
            }
        )

    # Largest, most-confident themes first.
    clusters.sort(key=lambda c: (-c["ticket_count"], -c["avg_similarity"]))
    return clusters
