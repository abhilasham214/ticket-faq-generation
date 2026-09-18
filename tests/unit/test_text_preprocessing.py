from api._lib.text_preprocessing import COMBINED_STOP_WORDS, preprocess_text


def test_lowercases_and_strips_punctuation():
    assert preprocess_text("Cannot Log In!!") == "cannot log in"


def test_collapses_whitespace():
    assert preprocess_text("too   many\nspaces") == "too many spaces"


def test_handles_empty_and_none_like_input():
    assert preprocess_text("") == ""


def test_generic_support_words_are_in_combined_stop_words():
    for word in ("issue", "problem", "error", "unable", "user", "please", "resolved", "checked", "fixed"):
        assert word in COMBINED_STOP_WORDS


def test_technical_terms_are_not_stop_words():
    for word in ("payment", "invoice", "api", "endpoint", "token", "password", "sso", "certificate", "webhook"):
        assert word not in COMBINED_STOP_WORDS
