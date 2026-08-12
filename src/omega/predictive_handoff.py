"""Predictive ground-station pre-position and handoff simulation.

Uses a review-grade J2 secular-rate + Kepler model, rotates predicted ECI
positions into ECEF, and returns planning artifacts only. No antenna commands or
operational acquisition-time claims are made.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

MU_EARTH_M3_S2 = 3.986004418e14
R_EARTH_M = 6_378_137.0
J2 = 1.08262668e-3
OMEGA_E_RAD_S = 7.2921159e-5


@dataclass(frozen=True)
class PredictedPass:
    satellite_id: int
    rise_time_s: float
    set_time_s: float
    max_elevation_deg: float
    rise_azimuth_deg: float
    set_azimuth_deg: float
    pre_position_time_s: float
    predicted_positions: list[dict]


@dataclass
class AntennaState:
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    is_tracking: bool = False
    current_satellite: Optional[int] = None
    last_update_s: float = 0.0


class OrbitalPredictor:
    def predict_position(
        self,
        a: float,
        e: float,
        i: float,
        raan: float,
        argp: float,
        mean_anomaly: float,
        time_s: float,
    ) -> tuple[float, float, float]:
        """Approximate ECEF position from osculating-like elements at t=0.

        Angles are radians, semi-major axis is meters, and ``time_s`` is seconds.
        This is intentionally not an SGP4 or mission-ephemeris claim.
        """
        if not all(math.isfinite(v) for v in (a, e, i, raan, argp, mean_anomaly, time_s)):
            raise ValueError("orbital inputs must be finite")
        if a <= R_EARTH_M or not 0.0 <= e < 1.0 or time_s < 0.0:
            raise ValueError("invalid elliptical orbit inputs")
        n = math.sqrt(MU_EARTH_M3_S2 / a**3)
        p = a * (1.0 - e**2)
        raan_rate = -1.5 * n * J2 * (R_EARTH_M / p) ** 2 * math.cos(i)
        argp_rate = 0.75 * n * J2 * (R_EARTH_M / p) ** 2 * (5.0 * math.cos(i) ** 2 - 1.0)
        raan_t = raan + raan_rate * time_s
        argp_t = argp + argp_rate * time_s
        mean = (mean_anomaly + n * time_s) % (2.0 * math.pi)

        eccentric = mean
        for _ in range(32):
            delta = (eccentric - e * math.sin(eccentric) - mean) / (1.0 - e * math.cos(eccentric))
            eccentric -= delta
            if abs(delta) < 1e-13:
                break

        cos_e, sin_e = math.cos(eccentric), math.sin(eccentric)
        denom = 1.0 - e * cos_e
        cos_nu = (cos_e - e) / denom
        sin_nu = math.sqrt(1.0 - e * e) * sin_e / denom
        radius = a * denom
        x_orb, y_orb = radius * cos_nu, radius * sin_nu

        co, so = math.cos(raan_t), math.sin(raan_t)
        ci, si = math.cos(i), math.sin(i)
        cw, sw = math.cos(argp_t), math.sin(argp_t)
        x_eci = (co * cw - so * sw * ci) * x_orb + (-co * sw - so * cw * ci) * y_orb
        y_eci = (so * cw + co * sw * ci) * x_orb + (-so * sw + co * cw * ci) * y_orb
        z_eci = sw * si * x_orb + cw * si * y_orb

        theta = OMEGA_E_RAD_S * time_s
        ct, st = math.cos(theta), math.sin(theta)
        return ct * x_eci + st * y_eci, -st * x_eci + ct * y_eci, z_eci


class PredictiveHandoffManager:
    def __init__(self):
        self.predictor = OrbitalPredictor()
        self._antennas: dict[str, AntennaState] = {}
        self._satellite_orbits: dict[int, dict[str, float]] = {}
        self._handoff_log: list[dict] = []

    def register_antenna(self, name: str):
        if not name.strip() or name in self._antennas:
            raise ValueError("antenna name must be unique and non-empty")
        self._antennas[name] = AntennaState()

    def register_satellite(self, sat_id: int, a: float, e: float, i: float, raan: float, argp: float, mean_anomaly: float):
        if sat_id <= 0:
            raise ValueError("satellite id must be positive")
        # Validate by propagating the epoch once.
        self.predictor.predict_position(a, e, i, raan, argp, mean_anomaly, 0.0)
        self._satellite_orbits[sat_id] = {"a": a, "e": e, "i": i, "raan": raan, "argp": argp, "mean_anomaly": mean_anomaly}

    def predict_next_handoff(
        self,
        antenna_name: str,
        station_lat: float,
        station_lon: float,
        horizon_elev_deg: float = 5.0,
        prediction_window_s: float = 300.0,
        step_s: float = 10.0,
    ) -> Optional[dict]:
        if antenna_name not in self._antennas:
            raise KeyError(antenna_name)
        if prediction_window_s <= 0 or step_s <= 0:
            raise ValueError("prediction window and step must be > 0")
        earliest: tuple[float, int, float] | None = None
        steps = int(math.floor(prediction_window_s / step_s)) + 1
        for sat_id, orbit in sorted(self._satellite_orbits.items()):
            for index in range(steps):
                offset = min(prediction_window_s, index * step_s)
                x, y, z = self.predictor.predict_position(**orbit, time_s=offset)
                elevation = self._compute_elevation(station_lat, station_lon, x, y, z)
                if elevation >= horizon_elev_deg:
                    candidate = (offset, sat_id, elevation)
                    if earliest is None or candidate[:2] < earliest[:2]:
                        earliest = candidate
                    break
        if earliest is None:
            return None
        offset, sat_id, elevation = earliest
        angles = self.compute_pre_position_angles(antenna_name, sat_id, station_lat, station_lon, offset)
        assert angles is not None
        return {
            "satellite_id": sat_id,
            "pre_position_time_s": offset,
            "predicted_elevation_deg": elevation,
            "predicted_azimuth_deg": angles["azimuth_deg"],
            "action": "PRE_POSITION_REVIEW",
            "antenna": antenna_name,
            "operational_authority": False,
        }

    def compute_pre_position_angles(self, antenna_name: str, sat_id: int, station_lat: float, station_lon: float, time_ahead_s: float) -> Optional[dict]:
        if antenna_name not in self._antennas:
            raise KeyError(antenna_name)
        orbit = self._satellite_orbits.get(sat_id)
        if orbit is None:
            return None
        x, y, z = self.predictor.predict_position(**orbit, time_s=time_ahead_s)
        azimuth, elevation = self._compute_az_el(station_lat, station_lon, x, y, z)
        return {
            "antenna": antenna_name,
            "satellite_id": sat_id,
            "azimuth_deg": azimuth,
            "elevation_deg": elevation,
            "time_ahead_s": time_ahead_s,
            "operational_authority": False,
        }

    def simulate_handoff(self, from_antenna: str, to_antenna: str, satellite_id: int, timestamp_s: float) -> dict:
        if from_antenna not in self._antennas or to_antenna not in self._antennas:
            raise KeyError("both antennas must be registered")
        if satellite_id not in self._satellite_orbits:
            raise KeyError("satellite must be registered")
        self._antennas[from_antenna].is_tracking = False
        self._antennas[from_antenna].current_satellite = None
        self._antennas[to_antenna].is_tracking = True
        self._antennas[to_antenna].current_satellite = satellite_id
        event = {
            "from": from_antenna,
            "to": to_antenna,
            "satellite": satellite_id,
            "timestamp_s": float(timestamp_s),
            "action": "SIMULATED_HANDOFF",
            "operational_authority": False,
        }
        self._handoff_log.append(event)
        return event

    def execute_handoff(self, from_antenna: str, to_antenna: str, satellite_id: int) -> dict:
        """Compatibility alias. This still performs simulation only."""
        return self.simulate_handoff(from_antenna, to_antenna, satellite_id, 0.0)

    @staticmethod
    def _station_position(lat_deg: float, lon_deg: float) -> tuple[float, float, float]:
        lat, lon = math.radians(lat_deg), math.radians(lon_deg)
        return R_EARTH_M * math.cos(lat) * math.cos(lon), R_EARTH_M * math.cos(lat) * math.sin(lon), R_EARTH_M * math.sin(lat)

    def _compute_elevation(self, lat_deg, lon_deg, sat_x, sat_y, sat_z):
        return self._compute_az_el(lat_deg, lon_deg, sat_x, sat_y, sat_z)[1]

    def _compute_az_el(self, lat_deg, lon_deg, sat_x, sat_y, sat_z):
        if not -90 <= lat_deg <= 90 or not -180 <= lon_deg <= 180:
            raise ValueError("invalid station latitude/longitude")
        lat, lon = math.radians(lat_deg), math.radians(lon_deg)
        gs_x, gs_y, gs_z = self._station_position(lat_deg, lon_deg)
        dx, dy, dz = sat_x - gs_x, sat_y - gs_y, sat_z - gs_z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        if distance <= 0:
            raise ValueError("satellite and station positions coincide")
        north = (-math.sin(lat) * math.cos(lon), -math.sin(lat) * math.sin(lon), math.cos(lat))
        east = (-math.sin(lon), math.cos(lon), 0.0)
        up = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
        vector = (dx, dy, dz)
        north_comp = sum(vector[j] * north[j] for j in range(3))
        east_comp = sum(vector[j] * east[j] for j in range(3))
        up_comp = sum(vector[j] * up[j] for j in range(3))
        azimuth = math.degrees(math.atan2(east_comp, north_comp)) % 360.0
        elevation = math.degrees(math.asin(max(-1.0, min(1.0, up_comp / distance))))
        return azimuth, elevation

    @property
    def network_status(self) -> dict:
        tracking = sum(1 for antenna in self._antennas.values() if antenna.is_tracking)
        return {
            "total_antennas": len(self._antennas),
            "tracking": tracking,
            "idle": len(self._antennas) - tracking,
            "total_handoffs": len(self._handoff_log),
            "registered_satellites": len(self._satellite_orbits),
            "operational_authority": False,
        }
