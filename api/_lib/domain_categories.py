"""Curated support-domain taxonomy shared by clustering and cluster naming.

This is the one piece of "domain knowledge" injected into an otherwise pure
keyword/TF-IDF pipeline. Each category is a short list of fairly specific
trigger phrases for a common SaaS-support domain, plus a human-readable
label used when a cluster is confidently dominated by that domain.

Deliberately NOT used: ML classifiers, embeddings, or an LLM. This is a
plain substring-match lookup table, so a cluster's category assignment is
always traceable to "these exact phrases were present in these tickets."

Keywords are kept fairly specific (e.g. "card declined" rather than bare
"card") to avoid false-positive matches on incidental generic wording -
see clustering.py's module docstring for why that matters.
"""

from typing import Any, Dict, List, Optional, TypedDict


class Category(TypedDict):
    label: str
    keywords: list


CATEGORIES: Dict[str, Category] = {
    "auth": {
        "label": "Login & Authentication Issues",
        "keywords": [
            "password", "login", "log in", "logins", "locked out",
            "session cookie", "credential", "sso", "certificate",
            "identity provider", "unlock", "invalid credentials", "signin",
            "two-factor", "mfa",
        ],
    },
    "billing": {
        "label": "Billing & Payment Issues",
        "keywords": [
            "invoice", "duplicate charge", "billing", "refund", "subscription",
            "credit card", "card declined", "declined", "transaction",
            "payment gateway", "prorated", "account balance",
        ],
    },
    "api": {
        "label": "API Authentication & Rate Limit Issues",
        "keywords": [
            "api", "endpoint", "rate limit", "api key", "webhook",
            "integration", "bulk import", "batching", "401 unauthorized",
            "429", "x-ratelimit", "authorization",
        ],
    },
    "data": {
        "label": "Data Export & Import Issues",
        "keywords": [
            "csv export", "csv import", "data export", "export job",
            "import job", "corrupted archive", "read replica", "importer",
            "export button",
        ],
    },
    "email": {
        "label": "Email & Notification Delivery Issues",
        "keywords": [
            "spam folder", "unsubscribe", "inbox", "delivery", "dmarc",
            "spf", "dkim", "digest", "notification email",
            "duplicate notification", "transactional email",
        ],
    },
}

# Prefix used for the synthetic tokens woven into clustering text by
# clustering.py, and filtered back out when extracting human-facing
# keywords in cluster_naming.py.
TAG_PREFIX = "cattag_"


def tag_categories(full_text: str, categories: Optional[Dict[str, Category]] = None) -> list:
    """Return the category ids whose trigger phrases appear in `full_text`.

    `full_text` should already be lowercased (e.g. via preprocess_text).
    A ticket may match zero, one, or several categories.

    `categories` defaults to the static curated CATEGORIES; callers that have
    merged in user-approved custom categories (see `merged_categories`) pass
    that combined dict instead, so a promoted theme gets the same clustering
    bridging boost as a built-in one.
    """
    categories = categories if categories is not None else CATEGORIES
    return [
        category_id
        for category_id, category in categories.items()
        if any(keyword in full_text for keyword in category["keywords"])
    ]


def merged_categories(custom_categories: List[Dict[str, Any]]) -> Dict[str, Category]:
    """Combine the static curated CATEGORIES with user-approved custom ones
    (as stored by category_store.list_custom_categories - each shaped like
    {"id", "label", "keywords"}), for a single request's clustering/naming.

    This never mutates CATEGORIES itself - custom categories only ever live
    in the persistent store, so the curated taxonomy in this file stays a
    reliable, code-reviewed source of truth.
    """
    merged: Dict[str, Category] = dict(CATEGORIES)
    for custom in custom_categories:
        merged[custom["id"]] = {"label": custom["label"], "keywords": custom["keywords"]}
    return merged
