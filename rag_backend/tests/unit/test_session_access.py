from types import SimpleNamespace

from app.security.session_access import can_access_session


def test_session_requires_matching_user_and_tenant():
    session = SimpleNamespace(user_id="user-1", tenant_id="tenant-1")

    assert can_access_session(session, "user-1", "tenant-1") is True
    assert can_access_session(session, "user-2", "tenant-1") is False
    assert can_access_session(session, "user-1", "tenant-2") is False


def test_missing_or_legacy_unscoped_session_is_denied():
    legacy_session = SimpleNamespace(user_id="user-1", tenant_id=None)

    assert can_access_session(None, "user-1", "tenant-1") is False
    assert can_access_session(legacy_session, "user-1", "tenant-1") is False
