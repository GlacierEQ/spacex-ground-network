"""Ground station network manager — station selection, handoff, link budget.

Optimizes ground station assignment based on elevation, load, and link margin.
Manages handoff sequencing during satellite passes.
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from alpha.antenna_tracker import (
    GroundStation, ECEF, LookAngles, compute_look_angles,
    doppler_shift, C,
)


@dataclass
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

    @property
    def eirp_dbw(self) -> float:
        return self.tx_power_dbw + self.tx_gain_db

    @property
    def free_space_loss_db(self) -> float:
        wavelength = C / self.freq_hz
        return 20 * math.log10(4 * math.pi * self.range_m / wavelength)

    @property
    def cn_ratio_db(self) -> float:
        k = 1.380649e-23
        noise_power = k * self.system_noise_temp_k * self.bandwidth_hz
        noise_db = 10 * math.log10(noise_power)

        rx_power_dbw = (
            self.eirp_dbw
            - self.free_space_loss_db
            - self.atmospheric_loss_db
            - self.pointing_loss_db
            + self.rx_gain_db
        )
        return rx_power_dbw - noise_db

    @property
    def link_margin_db(self) -> float:
        return self.cn_ratio_db - 10.0

    @property
    def is_viable(self) -> bool:
        return self.link_margin_db > 0


@dataclass
class StationStatus:
    station: GroundStation
    elevation: float = 0.0
    azimuth: float = 0.0
    range_km: float = 0.0
    link_margin_db: float = 0.0
    load_percent: float = 0.0
    active: bool = True


@dataclass
class HandoffEvent:
    time: float
    from_station: str
    to_station: str
    reason: str
    elevation_from: float = 0.0
    elevation_to: float = 0.0


class NetworkManager:
    def __init__(self):
        self.stations: list[GroundStation] = []
        self._statuses: dict[str, StationStatus] = {}
        self._handoff_log: list[HandoffEvent] = []
        self._active_station: Optional[str] = None

    def add_station(self, station: GroundStation):
        self.stations.append(station)
        self._statuses[station.name] = StationStatus(station=station)

    def update_satellite(
        self, sat_ecef: ECEF, sat_vel: tuple[float, float, float], time: float
    ) -> dict:
        for station in self.stations:
            angles = compute_look_angles(station, sat_ecef)
            link = LinkBudget(
                tx_power_dbw=20.0,
                tx_gain_db=35.0,
                freq_hz=station.frequency_hz,
                range_m=angles.range_m,
            )

            status = self._statuses[station.name]
            status.elevation = angles.elevation
            status.azimuth = angles.azimuth
            status.range_km = angles.range_m / 1000
            status.link_margin_db = link.link_margin_db

        return self._select_station(time)

    def _select_station(self, time: float) -> dict:
        candidates = [
            (name, s) for name, s in self._statuses.items()
            if s.active and s.elevation > s.station.min_elevation
        ]

        if not candidates:
            return {"action": "NO_COVERAGE", "station": None}

        candidates.sort(key=lambda x: x[1].link_margin_db, reverse=True)
        best_name, best_status = candidates[0]

        if self._active_station and self._active_station != best_name:
            event = HandoffEvent(
                time=time,
                from_station=self._active_station,
                to_station=best_name,
                reason="better_link_margin",
                elevation_from=self._statuses[self._active_station].elevation,
                elevation_to=best_status.elevation,
            )
            self._handoff_log.append(event)

        self._active_station = best_name

        return {
            "action": "TRACKING",
            "station": best_name,
            "elevation": round(best_status.elevation, 2),
            "link_margin_db": round(best_status.link_margin_db, 2),
            "range_km": round(best_status.range_km, 1),
        }

    @property
    def active_station(self) -> Optional[str]:
        return self._active_station

    @property
    def handoff_history(self) -> list[dict]:
        return [
            {
                "time": h.time,
                "from": h.from_station,
                "to": h.to_station,
                "reason": h.reason,
            }
            for h in self._handoff_log
        ]

    @property
    def network_health(self) -> dict:
        total = len(self.stations)
        visible = sum(
            1 for s in self._statuses.values()
            if s.elevation > s.station.min_elevation
        )
        return {
            "total_stations": total,
            "visible_satellite": visible,
            "active_station": self._active_station,
            "handoff_count": len(self._handoff_log),
        }


def create_f9_ground_network() -> NetworkManager:
    """Pre-configured SpaceX ground station network."""
    nm = NetworkManager()

    from alpha.antenna_tracker import LLA
    stations = [
        GroundStation("Vandenberg", LLA(34.7, -120.6, 0.0), 2.0e9),
        GroundStation("Cape Canaveral", LLA(28.5, -80.6, 0.0), 2.0e9),
        GroundStation("Kwajalein", LLA(9.4, 167.7, 0.0), 2.0e9),
    ]

    for s in stations:
        nm.add_station(s)

    return nm
