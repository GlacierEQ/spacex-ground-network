"""Ground network tests."""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from alpha.antenna_tracker import (
    LLA, ECEF, GroundStation, lla_to_ecef, ecef_to_lla,
    compute_look_angles, doppler_shift, LookAngles,
)
from omega.network_manager import (
    NetworkManager, LinkBudget, StationStatus, create_f9_ground_network,
)

R_EARTH = 6378137.0
TOL = 1e-3


def test_lla_to_ecef_equator():
    ecef = lla_to_ecef(LLA(0, 0, 0))
    assert abs(ecef.x - R_EARTH) < 1.0
    assert abs(ecef.y) < 1.0
    assert abs(ecef.z) < 1.0


def test_lla_to_ecef_pole():
    ecef = lla_to_ecef(LLA(90, 0, 0))
    assert abs(ecef.x) < 1.0
    assert abs(ecef.y) < 1.0
    R_POLAR = 6356752.3
    assert abs(ecef.z - R_POLAR) < 1.0


def test_lla_to_ecef_roundtrip():
    original = LLA(28.5, -80.6, 400000)
    ecef = lla_to_ecef(original)
    recovered = ecef_to_lla(ecef)

    assert abs(recovered.lat - original.lat) < 0.001
    assert abs(recovered.lon - original.lon) < 0.001
    assert abs(recovered.alt - original.alt) < 100


def test_look_angles_overhead():
    station = GroundStation("test", LLA(0, 0, 0))
    sat_ecef = ECEF(R_EARTH + 400000, 0, 0)

    angles = compute_look_angles(station, sat_ecef)
    assert angles.elevation > 80.0
    assert angles.range_m > 300000


def test_look_angles_horizon():
    station = GroundStation("test", LLA(0, 0, 0))
    ecef = lla_to_ecef(LLA(0, 90, 400000))

    angles = compute_look_angles(station, ecef)
    assert angles.elevation < 45.0


def test_doppler_shift_approaching():
    station = GroundStation("test", LLA(0, 0, 0), frequency_hz=8e9)
    sat_ecef = ECEF(R_EARTH + 400000, 0, 0)
    sat_vel = (-7800, 0, 0)

    dop = doppler_shift(station, sat_ecef, sat_vel)
    assert dop > 0


def test_link_budget_viable():
    link = LinkBudget(
        tx_power_dbw=20.0,
        tx_gain_db=35.0,
        freq_hz=2e9,
        range_m=400000,
    )
    assert link.eirp_dbw == 55.0
    assert link.free_space_loss_db > 150
    assert link.is_viable


def test_network_manager():
    nm = NetworkManager()
    nm.add_station(GroundStation("S1", LLA(0, 0, 0)))
    nm.add_station(GroundStation("S2", LLA(0, 10, 0)))

    sat_ecef = ECEF(R_EARTH + 400000, 0, 0)
    result = nm.update_satellite(sat_ecef, (0, 7800, 0), 0.0)

    assert result["station"] in ("S1", "S2") or result["action"] == "NO_COVERAGE"
    assert nm.network_health["total_stations"] == 2


def test_f9_ground_network():
    nm = create_f9_ground_network()
    assert len(nm.stations) == 3


def test_handoff():
    nm = NetworkManager()
    nm.add_station(GroundStation("S1", LLA(0, 0, 0)))
    nm.add_station(GroundStation("S2", LLA(0, 5, 0)))

    sat1 = ECEF(R_EARTH + 400000, 0, 0)
    nm.update_satellite(sat1, (0, 7800, 0), 0.0)
    first = nm.active_station

    sat2 = ECEF(R_EARTH + 400000, 0, 500000)
    nm.update_satellite(sat2, (0, 7800, 0), 10.0)

    if nm.active_station != first:
        assert len(nm.handoff_history) >= 1


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
