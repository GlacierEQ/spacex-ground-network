"""Deterministic ground-station network selection, link budget and handoff logic.

This module performs local planning only. It emits review decisions and has no
RF transmit, command-uplink, antenna-actuation, or spacecraft authority.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from alpha.antenna_tracker import C, ECEF, GroundStation, LLA, compute_look_angles, doppler_shift

BOLTZMANN_J_K = 1.380649e-23


@dataclass(frozen=True)
class LinkBudget:
    tx_power_dbw: float
    tx_gain_db: float
    freq_hz: float
    range_m: float
    atmospheric_loss_db: float = 0.5
    pointing_loss_db: float = 0.3
    rx_gain_db: float = 40.0
    system_noise_temp_k: float = 290.0
    bandwidth_hz: float = 1e6
    required_cn_db: float = 10.0

    def __post_init__(self) -> None:
        values = (
            self.tx_power_dbw, self.tx_gain_db, self.freq_hz, self.range_m,
            self.atmospheric_loss_db, self.pointing_loss_db, self.rx_gain_db,
            self.system_noise_temp_k, self.bandwidth_hz, self.required_cn_db,
        )
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("link budget values must be finite")
        if self.freq_hz <= 0 or self.range_m <= 0 or self.system_noise_temp_k <= 0 or self.bandwidth_hz <= 0:
            raise ValueError("frequency, range, noise temperature and bandwidth must be > 0")

    @property
    def eirp_dbw(self) -> float:
        return self.tx_power_dbw + self.tx_gain_db

    @property
    def free_space_loss_db(self) -> float:
        wavelength = C / self.freq_hz
        return 20.0 * math.log10(4.0 * math.pi * self.range_m / wavelength)

    @property
    def received_power_dbw(self) -> float:
        return self.eirp_dbw - self.free_space_loss_db - self.atmospheric_loss_db - self.pointing_loss_db + self.rx_gain_db

    @property
    def noise_power_dbw(self) -> float:
        return 10.0 * math.log10(BOLTZMANN_J_K * self.system_noise_temp_k * self.bandwidth_hz)

    @property
    def cn_ratio_db(self) -> float:
        return self.received_power_dbw - self.noise_power_dbw

    @property
    def link_margin_db(self) -> float:
        return self.cn_ratio_db - self.required_cn_db

    @property
    def is_viable(self) -> bool:
        return self.link_margin_db >= 0.0


@dataclass
class StationStatus:
    station: GroundStation
    elevation: float = -90.0
    azimuth: float = 0.0
    range_km: float = float("inf")
    link_margin_db: float = float("-inf")
    doppler_hz: float = 0.0
    load_percent: float = 0.0
    active: bool = True

    def validate(self) -> None:
        if not 0.0 <= self.load_percent <= 100.0:
            raise ValueError("load_percent must be in [0, 100]")


@dataclass(frozen=True)
class HandoffEvent:
    time: float
    from_station: str
    to_station: str
    reason: str
    elevation_from: float = 0.0
    elevation_to: float = 0.0


class NetworkManager:
    def __init__(self, *, handoff_hysteresis_db: float = 2.0, max_station_load_percent: float = 95.0):
        if handoff_hysteresis_db < 0 or not 0 < max_station_load_percent <= 100:
            raise ValueError("invalid network selection thresholds")
        self.handoff_hysteresis_db = float(handoff_hysteresis_db)
        self.max_station_load_percent = float(max_station_load_percent)
        self.stations: list[GroundStation] = []
        self._statuses: dict[str, StationStatus] = {}
        self._handoff_log: list[HandoffEvent] = []
        self._active_station: Optional[str] = None

    def add_station(self, station: GroundStation):
        if station.name in self._statuses:
            raise ValueError(f"duplicate station: {station.name}")
        self.stations.append(station)
        self._statuses[station.name] = StationStatus(station=station)

    def set_station_health(self, station_name: str, *, active: bool | None = None, load_percent: float | None = None) -> None:
        if station_name not in self._statuses:
            raise KeyError(station_name)
        status = self._statuses[station_name]
        if active is not None:
            status.active = bool(active)
        if load_percent is not None:
            status.load_percent = float(load_percent)
            status.validate()
        if self._active_station == station_name and not status.active:
            self._active_station = None

    def update_satellite(self, sat_ecef: ECEF, sat_vel: tuple[float, float, float], time: float) -> dict:
        for station in self.stations:
            angles = compute_look_angles(station, sat_ecef)
            link = LinkBudget(20.0, 35.0, station.frequency_hz, angles.range_m)
            status = self._statuses[station.name]
            status.elevation = angles.elevation
            status.azimuth = angles.azimuth
            status.range_km = angles.range_m / 1000.0
            status.link_margin_db = link.link_margin_db
            status.doppler_hz = doppler_shift(station, sat_ecef, sat_vel)
        return self._select_station(float(time))

    def _score(self, status: StationStatus) -> float:
        """Prefer link margin while reserving loaded stations for existing work."""
        return status.link_margin_db - 0.05 * status.load_percent

    def _eligible(self, status: StationStatus) -> bool:
        return (
            status.active
            and status.elevation >= status.station.min_elevation
            and status.link_margin_db >= 0.0
            and status.load_percent < self.max_station_load_percent
        )

    def _select_station(self, time: float) -> dict:
        eligible = [(name, status) for name, status in self._statuses.items() if self._eligible(status)]
        if not eligible:
            previous = self._active_station
            self._active_station = None
            return {"action": "NO_COVERAGE", "station": None, "previous_station": previous, "operational_authority": False}

        eligible.sort(key=lambda item: (-self._score(item[1]), item[0]))
        best_name, best = eligible[0]

        if self._active_station is not None and self._active_station in self._statuses:
            current = self._statuses[self._active_station]
            if self._eligible(current) and self._active_station != best_name:
                if self._score(best) < self._score(current) + self.handoff_hysteresis_db:
                    best_name, best = self._active_station, current

        if self._active_station and self._active_station != best_name:
            old = self._statuses[self._active_station]
            self._handoff_log.append(HandoffEvent(time, self._active_station, best_name, "better_viable_score", old.elevation, best.elevation))

        self._active_station = best_name
        return {
            "action": "TRACKING_REVIEW",
            "station": best_name,
            "azimuth_deg": round(best.azimuth, 3),
            "elevation_deg": round(best.elevation, 3),
            "link_margin_db": round(best.link_margin_db, 3),
            "range_km": round(best.range_km, 3),
            "doppler_hz": round(best.doppler_hz, 3),
            "station_load_percent": round(best.load_percent, 3),
            "operational_authority": False,
        }

    def screen_contact_series(self, samples: list[tuple[ECEF, tuple[float, float, float], float]]) -> list[dict]:
        """Evaluate a deterministic sequence and record only state changes."""
        events: list[dict] = []
        previous: tuple[str, Optional[str]] | None = None
        for position, velocity, timestamp in samples:
            result = self.update_satellite(position, velocity, timestamp)
            state = (str(result["action"]), result["station"])
            if state != previous:
                events.append({"time": timestamp, **result})
                previous = state
        return events

    @property
    def active_station(self) -> Optional[str]:
        return self._active_station

    @property
    def handoff_history(self) -> list[dict]:
        return [{"time": event.time, "from": event.from_station, "to": event.to_station, "reason": event.reason} for event in self._handoff_log]

    @property
    def network_health(self) -> dict:
        visible = sum(1 for status in self._statuses.values() if self._eligible(status))
        return {
            "total_stations": len(self.stations),
            "eligible_stations": visible,
            "active_station": self._active_station,
            "handoff_count": len(self._handoff_log),
            "operational_authority": False,
        }


def create_f9_ground_network() -> NetworkManager:
    """Compatibility demo topology using public geographic labels only."""
    manager = NetworkManager()
    for station in (
        GroundStation("Vandenberg-demo", LLA(34.7, -120.6, 0.0), 2.0e9),
        GroundStation("Cape-demo", LLA(28.5, -80.6, 0.0), 2.0e9),
        GroundStation("Kwajalein-demo", LLA(9.4, 167.7, 0.0), 2.0e9),
    ):
        manager.add_station(station)
    return manager
