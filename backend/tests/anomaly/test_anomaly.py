from __future__ import annotations

import axelcompta.anomaly as anomaly


def test_la_facade_expose_analyser() -> None:
    assert callable(anomaly.analyser)
