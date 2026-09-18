"""Shared text-cleaning helpers used before TF-IDF vectorization."""

import re
import string

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Words that are common in support-ticket prose but carry no signal about
# *which* recurring issue a ticket belongs to. Removed on top of sklearn's
# standard English stop words so clusters form around technical/domain
# nouns (payment, endpoint, certificate, ...) instead of ticket-boilerplate
# verbs (resolved, checked, fixed, ...).
GENERIC_SUPPORT_WORDS = frozenset(
    {
        "issue", "issues", "problem", "problems", "error", "errors", "unable",
        "user", "users", "please", "resolved", "resolve", "checked", "fixed",
        "fix", "ticket", "tickets", "customer", "customers", "support", "team",
        "contact", "contacted", "request", "requested", "reported", "confirmed",
        "confirming", "working", "work", "now", "still", "also", "would",
        "could", "asked", "found", "showing", "shows", "show", "reports",
        "says", "say",
    }
)

COMBINED_STOP_WORDS = frozenset(ENGLISH_STOP_WORDS) | GENERIC_SUPPORT_WORDS

_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")
_WHITESPACE_RE = re.compile(r"\s+")


def preprocess_text(text: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace.

    Stopword removal happens separately (via COMBINED_STOP_WORDS passed to
    TfidfVectorizer) rather than here, so that bigrams like "rate limit" are
    formed from adjacent surviving tokens before either word could be
    dropped by this step.
    """
    text = (text or "").lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text
