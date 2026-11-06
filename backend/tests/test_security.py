from auth.security import generate_state, verify_state


def test_generate_state_is_unique_and_url_safe():
    first = generate_state()
    second = generate_state()
    assert first != second
    assert all(char.isalnum() or char in "-_" for char in first)


def test_verify_state_edge_cases():
    assert verify_state("saved", "saved") is True
    assert verify_state("saved", "other") is False
    assert verify_state("", "") is False
    assert verify_state(None, "saved") is False
    assert verify_state("saved", None) is False
    assert verify_state(None, None) is False
