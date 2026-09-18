"""Deterministic, rule-based cluster theme naming - no LLM involved.

Gemini is used for exactly one thing in this app: drafting the FAQ text for
an already-formed cluster (see faq_drafting.py). Naming the cluster itself
happens here, from the cluster's top TF-IDF terms, so a theme name is
always traceable to "these words were the strongest signal in this
cluster" rather than a model's guess.

Two tiers:
  1. Match the cluster's top terms against the curated domain taxonomy in
     domain_categories.py, then a small set of sub-rules picks between a
     couple of named variants per domain (e.g. billing tickets dominated by
     "invoice"/"duplicate charge" are named differently from ones dominated
     by "payment"/"transaction"/"gateway") - this is what produces names
     like the ones in the spec ("Billing & Duplicate Charge Issues",
     "SSO Authentication & Certificate Issues").
  2. If no domain confidently matches, fall back to composing a name
     directly from the top 1-2 meaningful terms (bigrams preferred, since
     they're more descriptive than single words), or - if even that isn't
     confident - "Recurring Issue: <top term>".
"""

from typing import Dict, List, Optional

from .domain_categories import CATEGORIES, Category

# Sub-rules checked in order for a cluster whose top terms best match a
# given category. Each rule is (required-any-of-these-terms, label); the
# first rule whose trigger terms intersect the cluster's keywords wins.
# The last rule in each list is the category's generic fallback label.
_SUB_RULES = {
    "auth": [
        ({"sso", "certificate", "identity provider"}, "SSO Authentication & Certificate Issues"),
        ({"password", "reset", "credential", "unlock", "locked"}, "Password Reset & Account Recovery"),
        (set(), "Login & Authentication Issues"),
    ],
    "billing": [
        ({"invoice", "duplicate charge", "duplicate"}, "Billing & Duplicate Charge Issues"),
        ({"payment", "transaction", "gateway", "payment gateway"}, "Payment & Transaction Issues"),
        (set(), "Billing & Payment Issues"),
    ],
    "api": [
        ({"rate limit", "429", "401", "key", "token", "authorization"}, "API Authentication & Rate Limit Issues"),
        (set(), "API Integration Issues"),
    ],
    "data": [
        (set(), "Data Export & Import Issues"),
    ],
    "email": [
        (set(), "Email & Notification Delivery Issues"),
    ],
}


def _best_matching_category(
    keywords: List[str], categories: Optional[Dict[str, Category]] = None
) -> Optional[str]:
    """Pick the domain category most strongly related to this cluster.

    A keyword "relates to" a category if it's a substring of one of the
    category's trigger phrases or vice versa (e.g. cluster keyword "rate
    limit" matches category keyword "rate limit"; cluster keyword "sso"
    matches category keyword "sso"). Plain substring matching, same spirit
    as the clustering-time tagging in domain_categories.tag_categories.

    Matches are weighted by the keyword's rank in `keywords` (already
    sorted strongest-first by TF-IDF weight), not just counted, so one
    strong top-ranked match outweighs a coincidental weak one further down
    the list (e.g. "password" outranking an incidental "account" match).

    `categories` defaults to the static curated CATEGORIES; pass a dict from
    `domain_categories.merged_categories` to also match user-approved custom
    categories.
    """
    categories = categories if categories is not None else CATEGORIES
    scores: Dict[str, int] = {}
    for rank, kw in enumerate(keywords):
        rank_weight = len(keywords) - rank
        for category_id, category in categories.items():
            if any(kw in trigger or trigger in kw for trigger in category["keywords"]):
                scores[category_id] = scores.get(category_id, 0) + rank_weight

    if not scores:
        return None
    return max(scores.items(), key=lambda item: item[1])[0]


def _pick_sub_rule(
    category_id: str, keywords: List[str], categories: Optional[Dict[str, Category]] = None
) -> str:
    """Pick the sub-rule whose trigger matches the cluster's *highest-ranked*
    keyword, rather than checking rules in a fixed priority order. `keywords`
    is already sorted strongest-first by TF-IDF weight, so this makes the
    name reflect whichever concept actually dominates the cluster (e.g. a
    cluster with 3 password tickets and 1 SSO ticket gets named for
    password reset, not SSO, because "password" outranks "sso").

    A custom category (added via category_store, not one of the 5 built-in
    ids) has no entry in _SUB_RULES, so this falls straight through to its
    own stored label.
    """
    categories = categories if categories is not None else CATEGORIES
    trigger_to_label = {}
    for trigger_terms, label in _SUB_RULES.get(category_id, []):
        for trigger in trigger_terms:
            trigger_to_label.setdefault(trigger, label)

    for kw in keywords:
        for trigger, label in trigger_to_label.items():
            if kw in trigger or trigger in kw:
                return label

    return categories[category_id]["label"]


def _title_case_term(term: str) -> str:
    return " ".join(word.upper() if len(word) <= 3 and word.isupper() else word.capitalize() for word in term.split())


def _fallback_name(keywords: List[str]) -> str:
    if not keywords:
        return "Recurring Issue: General"

    # Prefer bigrams (contain a space) - more descriptive than lone words.
    bigrams = [k for k in keywords if " " in k]
    unigrams = [k for k in keywords if " " not in k]
    ordered = bigrams + unigrams

    if len(ordered) >= 2:
        first, second = ordered[0], ordered[1]
        return f"{_title_case_term(first)} & {_title_case_term(second)} Issues"

    return f"Recurring Issue: {_title_case_term(ordered[0])}"


def has_curated_match(keywords: List[str], categories: Optional[Dict[str, Category]] = None) -> bool:
    """True if `keywords` confidently matches one of the curated domains in
    `categories` (default: the static CATEGORIES). Used by the caller
    (api/index.py) to decide whether a cluster is an established theme or a
    candidate for Gemini-assisted naming via category_discovery.py - this
    module itself stays LLM-free either way.
    """
    return _best_matching_category(keywords, categories) is not None


def name_cluster(keywords: List[str], categories: Optional[Dict[str, Category]] = None) -> str:
    """Produce a 3-7 word, title-case theme name from a cluster's top TF-IDF terms.

    `keywords` should already exclude the synthetic category tag tokens
    used internally by clustering.py (clustering.py's _top_terms does this).

    `categories` defaults to the static curated CATEGORIES; pass a dict from
    `domain_categories.merged_categories` to also recognize user-approved
    custom categories.
    """
    category_id = _best_matching_category(keywords, categories)
    if category_id:
        return _pick_sub_rule(category_id, keywords, categories)

    return _fallback_name(keywords)
