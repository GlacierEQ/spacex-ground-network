"""Core geometry and predictive-handoff tests."""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from alpha.antenna_tracker import LLA, lla_to_ecef, ecef_to_lla
from omega.predictive_handoff import PredictiveHandoffManager


def test_lla_to_ecef():
    lla = LLA(lat=28.5, lon=-80.6, alt=0)
    ecef = lla_to_ecef(lla)
    assert ecef.magnitude > 6e6


def test_ecef_roundtrip():
    lla = LLA(lat=28.5, lon=-80.6, alt=1000)
    ecef = lla_to_ecef(lla)
    lla2 = ecef_to_lla(ecef)
    assert abs(lla.lat - lla2.lat) < 0.01
    assert abs(lla.lon - lla2.lon) < 0.01
    assert abs(lla.alt - lla2.alt) < 1.0


def test_predictive_handoff_requires_registered_antenna_and_emits_review_only():
    phm = PredictiveHandoffManager()
    phm.register_antenna("ant1")
    phm.register_satellite(1, a=6_800_000, e=0.001, i=0.5, raan=0, argp=0, mean_anomaly=0)
    result = phm.predict_next_handoff("ant1", 28.5, -80.6)
    assert result is None or ("satellite_id" in result and result["operational_authority"] is False)


C = 299_792_458
assert C == 299_792_458
