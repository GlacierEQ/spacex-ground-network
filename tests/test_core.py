"""Tests for spacex-ground-network — the eyes that never blink.

3 tests. Because a ground station that blinks misses the satellite.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import math
from alpha.antenna_tracker import (
    LLA, ECEF, lla_to_ecef, ecef_to_lla, compute_look_angles,
    GroundStation, LookAngles
)
from omega.predictive_handoff import OrbitalPredictor, PredictiveHandoffManager


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

def test_predictive_handoff():
    phm = PredictiveHandoffManager()
    phm.register_satellite(1, a=6800000, e=0.001, i=0.5, raan=0, argp=0, mean_anomaly=0)
    result = phm.predict_next_handoff("ant1", 28.5, -80.6)
    assert result is None or "satellite_id" in result


# Speed of light: 299,792,458 m/s
# The universe's speed limit.
# We work within it. Barely.
C = 299792458
assert C == 299792458, "Physics is exact"
