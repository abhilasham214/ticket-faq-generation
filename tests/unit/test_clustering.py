import pytest

from api._lib.clustering import ClusteringError, cluster_tickets


def _ticket(external_id, subject, description, resolution):
    return {
        "external_id": external_id,
        "subject": subject,
        "description": description,
        "resolution": resolution,
    }


LOGIN_TICKETS = [
    _ticket("L1", "Cannot log in", "Password reset link rejected", "Cleared stale session cookie"),
    _ticket("L2", "Locked out of account", "Too many failed login attempts", "Manually unlocked account"),
    _ticket("L3", "Login page blank", "SSO redirect shows blank page", "Rotated expired SSO certificate"),
    _ticket("L4", "Password reset email missing", "Reset email never arrives", "Removed address from suppression list"),
]

BILLING_TICKETS = [
    _ticket("B1", "Duplicate invoice charge", "Billed twice for one cycle", "Refunded duplicate charge"),
    _ticket("B2", "Invoice total mismatch", "Total higher than plan price", "Added prorated upgrade line item"),
    _ticket("B3", "Card declined silently", "Subscription downgraded with no notice", "Restored paid tier, notified user"),
    _ticket("B4", "Refund missing from balance", "Balance dashboard shows stale amount", "Forced cache refresh"),
]

API_TICKETS = [
    _ticket("A1", "API returns 429 errors", "Rate limited under normal usage", "Fixed rate limiter key"),
    _ticket("A2", "Rate limit headers missing", "No X-RateLimit headers in response", "Added rate limit headers"),
    _ticket("A3", "Bulk import times out", "Endpoint times out over 500 records", "Added batching and higher timeout"),
    _ticket("A4", "API key stopped working", "Key expired with no warning", "Issued new key, added expiry reminder"),
]


def test_cluster_count_lands_in_required_range():
    tickets = LOGIN_TICKETS + BILLING_TICKETS + API_TICKETS
    clusters = cluster_tickets(tickets)
    assert 3 <= len(clusters) <= 5


def test_cluster_ticket_counts_sum_to_total():
    tickets = LOGIN_TICKETS + BILLING_TICKETS + API_TICKETS
    clusters = cluster_tickets(tickets)
    assert sum(c["ticket_count"] for c in clusters) == len(tickets)


def test_each_cluster_has_top_terms():
    tickets = LOGIN_TICKETS + BILLING_TICKETS + API_TICKETS
    clusters = cluster_tickets(tickets)
    for cluster in clusters:
        assert len(cluster["top_terms"]) > 0


def test_raises_on_empty_ticket_list():
    with pytest.raises(ClusteringError):
        cluster_tickets([])


def test_handles_very_small_ticket_count_without_crashing():
    tickets = LOGIN_TICKETS[:2]
    clusters = cluster_tickets(tickets)
    assert sum(c["ticket_count"] for c in clusters) == len(tickets)
    assert len(clusters) >= 1
