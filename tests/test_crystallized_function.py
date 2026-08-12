from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from alpha.antenna_tracker import ECEF, GroundStation, LLA, R_EARTH, compute_look_angles, doppler_shift, ecef_to_lla, lla_to_ecef
from ground_network import evaluate_payload
from omega.network_manager import LinkBudget, NetworkManager
from omega.predictive_handoff import OrbitalPredictor, PredictiveHandoffManager


def test_wgs84_roundtrip_at_high_latitude():
    source = LLA(64.2, -149.5, 250.0)
    recovered = ecef_to_lla(lla_to_ecef(source))
    assert recovered.lat == pytest.approx(source.lat, abs=1e-8)
    assert recovered.lon == pytest.approx(source.lon, abs=1e-8)
    assert recovered.alt == pytest.approx(source.alt, abs=1e-4)


def test_overhead_geometry_and_doppler_sign():
    station = GroundStation("eq", LLA(0, 0, 0), 2e9)
    sat = ECEF(R_EARTH + 500_000, 0, 0)
    look = compute_look_angles(station, sat)
    assert look.elevation == pytest.approx(90.0, abs=1e-8)
    assert doppler_shift(station, sat, (-1000.0, 0.0, 0.0)) > 0


def test_link_budget_rejects_nonphysical_range():
    with pytest.raises(ValueError):
        LinkBudget(20, 35, 2e9, 0)


def test_network_skips_failed_and_negative_margin_candidates():
    manager = NetworkManager()
    good = GroundStation("good", LLA(0, 0, 0), 2e9)
    failed = GroundStation("failed", LLA(0, 0, 0), 2e9)
    manager.add_station(good)
    manager.add_station(failed)
    manager.set_station_health("failed", active=False)
    result = manager.update_satellite(ECEF(R_EARTH + 500_000, 0, 0), (0, 7500, 0), 0)
    assert result["station"] == "good"
    assert result["operational_authority"] is False


def test_load_penalty_changes_selection_when_links_are_close():
    manager = NetworkManager(handoff_hysteresis_db=0)
    manager.add_station(GroundStation("loaded", LLA(0, 0, 0), 2e9))
    manager.add_station(GroundStation("free", LLA(0, 0, 0), 2e9))
    manager.set_station_health("loaded", load_percent=90)
    manager.set_station_health("free", load_percent=0)
    result = manager.update_satellite(ECEF(R_EARTH + 500_000, 0, 0), (0, 7500, 0), 0)
    assert result["station"] == "free"


def test_hysteresis_prevents_chatter_for_small_score_delta():
    manager = NetworkManager(handoff_hysteresis_db=3)
    manager.add_station(GroundStation("A", LLA(0, 0, 0), 2e9))
    manager.add_station(GroundStation("B", LLA(0, 0, 0), 2e9))
    manager.set_station_health("A", load_percent=0)
    manager.set_station_health("B", load_percent=40)
    sat = ECEF(R_EARTH + 500_000, 0, 0)
    first = manager.update_satellite(sat, (0, 7500, 0), 0)
    assert first["station"] == "A"
    manager.set_station_health("A", load_percent=20)
    manager.set_station_health("B", load_percent=0)
    second = manager.update_satellite(sat, (0, 7500, 0), 1)
    assert second["station"] == "A"


def test_orbit_predictor_outputs_finite_earth_fixed_position():
    predictor = OrbitalPredictor()
    position = predictor.predict_position(6_800_000, 0.001, math.radians(51.6), 0, 0, 0, 120)
    assert len(position) == 3
    assert all(math.isfinite(v) for v in position)
    assert 6.0e6 < math.sqrt(sum(v*v for v in position)) < 8.0e6


def test_simulated_handoff_never_claims_zero_time_or_operational_authority():
    manager = PredictiveHandoffManager()
    manager.register_antenna("A")
    manager.register_antenna("B")
    manager.register_satellite(1, 6_800_000, 0.001, 0.5, 0, 0, 0)
    result = manager.simulate_handoff("A", "B", 1, 42.0)
    assert result["action"] == "SIMULATED_HANDOFF"
    assert result["timestamp_s"] == 42.0
    assert result["operational_authority"] is False
    assert "acquisition_time_ms" not in result


def test_payload_and_cli_produce_deterministic_truth_bounded_plan():
    payload = {
        "stations": [{"name": "eq", "lat_deg": 0, "lon_deg": 0, "frequency_hz": 2e9}],
        "samples": [{"time_s": 0, "ecef_m": [R_EARTH + 500_000, 0, 0], "velocity_ecef_mps": [0, 7500, 0]}],
    }
    result = evaluate_payload(payload)
    assert result["schema"] == "glaciereq.ground-network-plan.v1"
    assert result["events"][0]["station"] == "eq"
    assert result["operational_authority"] is False

    proc = subprocess.run([sys.executable, str(ROOT / "src" / "ground_network.py"), "demo"], check=True, capture_output=True, text=True)
    cli = json.loads(proc.stdout)
    assert cli["schema"] == "glaciereq.ground-network-plan.v1"
    assert cli["operational_authority"] is False
