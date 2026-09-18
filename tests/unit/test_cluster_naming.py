from api._lib.cluster_naming import has_curated_match, name_cluster


def test_payment_transaction_gateway_keywords():
    assert name_cluster(["payment", "transaction", "gateway"]) == "Payment & Transaction Issues"


def test_api_key_endpoint_rate_limit_keywords():
    assert name_cluster(["api", "key", "endpoint", "rate limit"]) == "API Authentication & Rate Limit Issues"


def test_password_reset_account_keywords():
    assert name_cluster(["password", "reset", "account"]) == "Password Reset & Account Recovery"


def test_invoice_charge_duplicate_keywords():
    assert name_cluster(["invoice", "charge", "duplicate"]) == "Billing & Duplicate Charge Issues"


def test_sso_certificate_identity_provider_keywords():
    assert name_cluster(["sso", "certificate", "identity provider"]) == "SSO Authentication & Certificate Issues"


def test_dominant_keyword_wins_over_lower_ranked_ones():
    """password ranks above sso -> name should reflect the majority topic."""
    assert name_cluster(["password", "reset", "sso"]) == "Password Reset & Account Recovery"


def test_name_is_never_a_slash_joined_keyword_list():
    for keywords in (
        ["api", "key", "endpoint"],
        ["password", "email", "reset"],
        ["webhook", "database", "timeout"],
    ):
        name = name_cluster(keywords)
        assert "/" not in name


def test_name_has_no_hallucinated_content_and_reasonable_length():
    name = name_cluster(["webhook", "database", "timeout"])
    assert 1 <= len(name.split()) <= 8
    assert not any(char.isdigit() for char in name)


def test_fallback_for_unrecognized_keywords_uses_safe_format():
    name = name_cluster(["frobnicate"])
    assert name.startswith("Recurring Issue:")


def test_empty_keywords_does_not_crash():
    name = name_cluster([])
    assert isinstance(name, str) and name


def test_has_curated_match_true_for_known_domain_keywords():
    assert has_curated_match(["password", "reset", "account"]) is True


def test_has_curated_match_false_for_unrecognized_keywords():
    assert has_curated_match(["frobnicate", "widget sync"]) is False
