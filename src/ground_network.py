#!/usr/bin/env python3
"""Executable ground-network planning simulator.

Consumes station definitions plus ECEF satellite states and emits deterministic
tracking-review decisions. No antenna actuation, RF transmission, command
uplink, spacecraft control, or operational network authority is provided.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from alpha.antenna_tracker import ECEF, GroundStation, LLA
from omega.network_manager import NetworkManager


def build_manager(stations: Sequence[Mapping[str, object]], *, handoff_hysteresis_db: float = 2.0) -> NetworkManager:
    if not stations:
        raise ValueError("at least one station is required")
    manager = NetworkManager(handoff_hysteresis_db=handoff_hysteresis_db)
    for item in stations:
        station = GroundStation(
            str(item["name"]),
            LLA(float(item["lat_deg"]), float(item["lon_deg"]), float(item.get("alt_m", 0.0))),
            float(item.get("frequency_hz", 2.0e9)),
            float(item.get("min_elevation_deg", 5.0)),
        )
        manager.add_station(station)
        manager.set_station_health(
            station.name,
            active=bool(item.get("active", True)),
            load_percent=float(item.get("load_percent", 0.0)),
        )
    return manager


def evaluate_payload(payload: Mapping[str, object]) -> dict:
    raw_stations = payload.get("stations")
    raw_samples = payload.get("samples")
    if not isinstance(raw_stations, list) or not isinstance(raw_samples, list) or not raw_samples:
        raise ValueError("stations and non-empty samples arrays are required")
    manager = build_manager(raw_stations, handoff_hysteresis_db=float(payload.get("handoff_hysteresis_db", 2.0)))
    samples = []
    for item in raw_samples:
        if not isinstance(item, Mapping):
            raise ValueError("each sample must be an object")
        pos = item["ecef_m"]
        vel = item.get("velocity_ecef_mps", [0.0, 0.0, 0.0])
        if not isinstance(pos, list) or len(pos) != 3 or not isinstance(vel, list) or len(vel) != 3:
            raise ValueError("ecef_m and velocity_ecef_mps must be 3-element arrays")
        samples.append((
            ECEF(float(pos[0]), float(pos[1]), float(pos[2])),
            (float(vel[0]), float(vel[1]), float(vel[2])),
            float(item.get("time_s", len(samples))),
        ))
    events = manager.screen_contact_series(samples)
    return {
        "schema": "glaciereq.ground-network-plan.v1",
        "events": events,
        "handoffs": manager.handoff_history,
        "network_health": manager.network_health,
        "operational_authority": False,
    }


def demo_payload() -> dict:
    earth = 6_378_137.0
    return {
        "stations": [
            {"name": "equator-west", "lat_deg": 0.0, "lon_deg": 0.0, "frequency_hz": 2e9, "load_percent": 15},
            {"name": "equator-east", "lat_deg": 0.0, "lon_deg": 8.0, "frequency_hz": 2e9, "load_percent": 20},
        ],
        "samples": [
            {"time_s": 0, "ecef_m": [earth + 500_000, 0, 0], "velocity_ecef_mps": [0, 7_500, 0]},
            {"time_s": 120, "ecef_m": [earth + 480_000, 500_000, 0], "velocity_ecef_mps": [-500, 7_450, 0]},
            {"time_s": 240, "ecef_m": [earth + 350_000, 1_000_000, 0], "velocity_ecef_mps": [-1_000, 7_350, 0]},
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic local ground-network planner")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("demo")
    simulate = sub.add_parser("plan")
    simulate.add_argument("input")
    args = parser.parse_args(argv)
    if args.command in (None, "demo"):
        result = evaluate_payload(demo_payload())
    else:
        import sys
        payload = json.load(sys.stdin) if args.input == "-" else json.loads(Path(args.input).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input must be a JSON object")
        result = evaluate_payload(payload)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
