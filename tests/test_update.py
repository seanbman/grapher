from grapher.update import ReleaseInfo, _key, update_available


def test_beta_version_ordering():
    assert _key("0.7.0b1") < _key("0.7.0")
    assert _key("0.7.0b2") > _key("0.7.0b1")
    assert _key("v0.8.0b1") > _key("0.7.0")


def test_update_available_accepts_prerelease():
    release = ReleaseInfo("v0.7.0b2", "0.7.0b2", "https://example.invalid", True)
    assert update_available("0.7.0b1", release) is True
    assert update_available("0.7.0b2", release) is False
