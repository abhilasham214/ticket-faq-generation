import pytest

from api._lib.clustering import ClusteringError, cluster_tickets


def _ticket(external_id, subject, resolution, description=""):
    return {
        "external_id": external_id,
        "subject": subject,
        "description": description,
        "resolution": resolution,
    }


LOGIN_TICKETS = [
    _ticket("L1", "Cannot log in after password reset", "Cleared stale session cookie, password reset worked"),
    _ticket("L2", "Locked out of account after failed logins", "Manually unlocked account, walked through password format"),
    _ticket("L3", "Password reset email never arrives", "Removed address from suppression list, resent reset link"),
    _ticket("L4", "SSO login redirects to blank page", "Identified expired SSO certificate, rotated the certificate"),
]

BILLING_TICKETS = [
    _ticket("B1", "Invoice shows duplicate charge", "Confirmed duplicate charge from retried webhook, refunded the duplicate charge"),
    _ticket("B2", "Invoice total mismatch with plan price", "Traced to a prorated upgrade charge, reissued the invoice"),
    _ticket("B3", "Credit card declined but subscription still active", "Restored paid tier after card was declined, backfilled access"),
    _ticket("B4", "Refund not reflected in account balance", "Forced a manual balance cache refresh, shortened cache TTL"),
]

API_TICKETS = [
    _ticket("A1", "API returns 429 errors under normal usage", "Fixed the rate limiter to key on api key and endpoint"),
    _ticket("A2", "Rate limit headers missing from API responses", "Added X-RateLimit headers to every api response"),
    _ticket("A3", "Bulk import API endpoint times out", "Added pagination and batching to the bulk import endpoint"),
    _ticket("A4", "API key stopped working with no warning", "Issued a new api key, added expiry reminder"),
]


def test_cluster_ticket_counts_sum_to_total():
    tickets = LOGIN_TICKETS + BILLING_TICKETS + API_TICKETS
    clusters = cluster_tickets(tickets)
    assert sum(c["ticket_count"] for c in clusters) == len(tickets)


def test_every_ticket_appears_exactly_once():
    tickets = LOGIN_TICKETS + BILLING_TICKETS + API_TICKETS
    clusters = cluster_tickets(tickets)
    seen = [tid for c in clusters for tid in c["ticket_ids"]]
    assert sorted(seen) == sorted(t["external_id"] for t in tickets)


def test_related_tickets_land_in_the_same_cluster():
    """The 3 clearly-distinct domains (login, billing, API) should not be
    scattered/merged into each other - each domain's tickets should share a
    cluster with at least one other ticket from the same domain."""
    tickets = LOGIN_TICKETS + BILLING_TICKETS + API_TICKETS
    clusters = cluster_tickets(tickets)

    def cluster_of(ticket_id):
        for c in clusters:
            if ticket_id in c["ticket_ids"]:
                return tuple(sorted(c["ticket_ids"]))
        raise AssertionError(f"{ticket_id} missing from clustering output")

    assert cluster_of("L1") == cluster_of("L2")
    assert cluster_of("B1") == cluster_of("B2")
    assert cluster_of("A1") == cluster_of("A2")


def test_unrelated_tickets_are_not_merged_on_generic_word_overlap():
    """A payment failure and an API key rejection share only generic words
    ("failed" / incidental overlap) and must not be forced together."""
    tickets = [
        _ticket("P1", "Payment failed after card update", "Card issuer declined the retry, asked customer to re-add card"),
        _ticket("P2", "Duplicate payment failed notification sent", "Fixed retry loop that re-sent the failure notice"),
        _ticket("K1", "API key rejected by endpoint", "Reissued a valid api key and updated the integration"),
        _ticket("K2", "API endpoint returns key rejected error", "Rotated the api key after it expired"),
    ]
    clusters = cluster_tickets(tickets)

    def cluster_of(ticket_id):
        for c in clusters:
            if ticket_id in c["ticket_ids"]:
                return tuple(sorted(c["ticket_ids"]))
        raise AssertionError(f"{ticket_id} missing from clustering output")

    assert cluster_of("P1") != cluster_of("K1")


def test_each_cluster_has_keywords():
    tickets = LOGIN_TICKETS + BILLING_TICKETS + API_TICKETS
    clusters = cluster_tickets(tickets)
    for cluster in clusters:
        assert len(cluster["keywords"]) > 0


def test_keywords_never_expose_internal_category_tags():
    tickets = LOGIN_TICKETS + BILLING_TICKETS + API_TICKETS
    clusters = cluster_tickets(tickets)
    for cluster in clusters:
        assert all(not kw.startswith("cattag_") for kw in cluster["keywords"])


def test_every_cluster_reports_similarity_info():
    tickets = LOGIN_TICKETS + BILLING_TICKETS + API_TICKETS
    clusters = cluster_tickets(tickets)
    for cluster in clusters:
        assert 0.0 <= cluster["avg_similarity"] <= 1.0 + 1e-9
        assert set(cluster["member_similarity"].keys()) == set(cluster["ticket_ids"])


def test_raises_on_empty_ticket_list():
    with pytest.raises(ClusteringError):
        cluster_tickets([])


def test_handles_very_small_ticket_count_without_crashing():
    tickets = LOGIN_TICKETS[:2]
    clusters = cluster_tickets(tickets)
    assert sum(c["ticket_count"] for c in clusters) == len(tickets)
    assert len(clusters) >= 1
