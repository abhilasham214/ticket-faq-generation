from typing import Any, Dict, List

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

MIN_K = 3
MAX_K = 5
TOP_TERMS_PER_CLUSTER = 6


class ClusteringError(ValueError):
    pass


def _ticket_text(ticket: Dict[str, Any]) -> str:
    return f"{ticket['subject']} {ticket['description']} {ticket['resolution']}"


def cluster_tickets(tickets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group tickets into 3-5 themes via TF-IDF + KMeans, auto-picking k by silhouette score.

    Each input ticket dict needs: subject, description, resolution, external_id.
    Returns a list of cluster dicts: {ticket_indices, ticket_ids, ticket_count, top_terms}.
    `ticket_indices` are positions into the input `tickets` list, so callers can map
    clusters back to their own identifiers (e.g. database primary keys).
    """
    n = len(tickets)
    if n == 0:
        raise ClusteringError("No tickets to cluster.")

    corpus = [_ticket_text(t) for t in tickets]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    matrix = vectorizer.fit_transform(corpus)
    matrix = normalize(matrix)
    terms = np.array(vectorizer.get_feature_names_out())

    max_k = min(MAX_K, n - 1)
    min_k = min(MIN_K, max_k) if max_k >= 1 else 1
    candidate_ks = [k for k in range(min_k, max_k + 1) if 1 < k < n]

    best_k = None
    best_score = -1.0
    best_labels = None

    for k in candidate_ks:
        model = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = model.fit_predict(matrix)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(matrix, labels)
        if score > best_score:
            best_score = score
            best_k = k
            best_labels = labels

    if best_labels is None:
        # Too few/too-similar tickets for a multi-cluster split - put everything in one theme.
        best_k = 1
        best_labels = np.zeros(n, dtype=int)

    clusters: List[Dict[str, Any]] = []
    for cluster_idx in range(best_k):
        member_indices = [i for i, label in enumerate(best_labels) if label == cluster_idx]
        if not member_indices:
            continue

        mean_vec = np.asarray(matrix[member_indices].mean(axis=0)).ravel()
        top_term_idx = mean_vec.argsort()[::-1][:TOP_TERMS_PER_CLUSTER]
        top_terms = [str(terms[i]) for i in top_term_idx if mean_vec[i] > 0]

        clusters.append(
            {
                "ticket_indices": member_indices,
                "ticket_ids": [tickets[i]["external_id"] for i in member_indices],
                "ticket_count": len(member_indices),
                "top_terms": top_terms,
            }
        )

    return clusters
