import re
from collections import Counter

from web_openness.signals import SIGNAL_KEYS


def test_signal_registry_is_unique_and_well_formed() -> None:
    assert len(SIGNAL_KEYS) == 110
    assert len(SIGNAL_KEYS) == len(set(SIGNAL_KEYS))
    assert all(re.fullmatch(r"[a-z]+\.[a-z0-9_]+", key) for key in SIGNAL_KEYS)


def test_signal_registry_has_expected_families() -> None:
    families = Counter(key.partition(".")[0] for key in SIGNAL_KEYS)

    assert families == {
        "agent": 9,
        "browser": 3,
        "crawler": 12,
        "economic": 6,
        "human": 17,
        "infrastructure": 21,
        "legal": 5,
        "metadata": 17,
        "network": 16,
        "preservation": 4,
    }
