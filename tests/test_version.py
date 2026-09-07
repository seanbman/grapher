import grapher


def test_release_version() -> None:
    assert grapher.__version__ == "0.7.0b1"
