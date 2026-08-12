"""Deterministic ground-station geometry, look angles, visibility and Doppler.

Coordinates are WGS-84 ECEF/LLA. Satellite velocity passed to ``doppler_shift``
is interpreted in the same ECEF frame as the satellite position.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

R_EARTH = 6_378_137.0
F = 1 / 298.257223563
E2 = 2 * F - F**2
C = 299_792_458.0


def _finite(name: str, value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True)
class LLA:
    lat: float
    lon: float
    alt: float

    def __post_init__(self) -> None:
        lat, lon, alt = _finite("lat", self.lat), _finite("lon", self.lon), _finite("alt", self.alt)
        if not -90.0 <= lat <= 90.0:
            raise ValueError("latitude must be in [-90, 90]")
        if not -180.0 <= lon <= 180.0:
            raise ValueError("longitude must be in [-180, 180]")
        object.__setattr__(self, "lat", lat)
        object.__setattr__(self, "lon", lon)
        object.__setattr__(self, "alt", alt)


@dataclass(frozen=True)
class ECEF:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        for name in ("x", "y", "z"):
            object.__setattr__(self, name, _finite(name, getattr(self, name)))

    def __sub__(self, other: "ECEF") -> "ECEF":
        return ECEF(self.x - other.x, self.y - other.y, self.z - other.z)

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.x**2 + self.y**2 + self.z**2)


@dataclass(frozen=True)
class LookAngles:
    azimuth: float
    elevation: float
    range_m: float
    range_rate: float = 0.0
    doppler_shift: float = 0.0


@dataclass
class GroundStation:
    name: str
    location: LLA
    frequency_hz: float = 8.1e9
    min_elevation: float = 5.0
    _ecef: ECEF = field(init=False, repr=False)

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("station name is required")
        self.frequency_hz = _finite("frequency_hz", self.frequency_hz)
        self.min_elevation = _finite("min_elevation", self.min_elevation)
        if self.frequency_hz <= 0 or not -5.0 <= self.min_elevation < 90.0:
            raise ValueError("invalid station frequency or elevation mask")
        self._ecef = lla_to_ecef(self.location)

    @property
    def ecef(self) -> ECEF:
        return self._ecef


def lla_to_ecef(lla: LLA) -> ECEF:
    lat, lon = math.radians(lla.lat), math.radians(lla.lon)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)
    n = R_EARTH / math.sqrt(1.0 - E2 * sin_lat**2)
    return ECEF(
        (n + lla.alt) * cos_lat * cos_lon,
        (n + lla.alt) * cos_lat * sin_lon,
        (n * (1.0 - E2) + lla.alt) * sin_lat,
    )


def ecef_to_lla(ecef: ECEF) -> LLA:
    x, y, z = ecef.x, ecef.y, ecef.z
    p = math.hypot(x, y)
    if p < 1e-9:
        lat = math.copysign(math.pi / 2.0, z)
        polar_radius = R_EARTH * math.sqrt(1.0 - E2)
        return LLA(math.degrees(lat), 0.0, abs(z) - polar_radius)
    lon = math.atan2(y, x)
    lat = math.atan2(z, p * (1.0 - E2))
    alt = 0.0
    for _ in range(12):
        sin_lat = math.sin(lat)
        n = R_EARTH / math.sqrt(1.0 - E2 * sin_lat**2)
        alt = p / math.cos(lat) - n
        new_lat = math.atan2(z, p * (1.0 - E2 * n / (n + alt)))
        if abs(new_lat - lat) < 1e-13:
            lat = new_lat
            break
        lat = new_lat
    return LLA(math.degrees(lat), math.degrees(lon), alt)


def ecef_to_sez(target: ECEF, reference: ECEF) -> tuple[float, float, float]:
    """ECEF delta to South-East-Zenith using WGS-84 geodetic latitude."""
    ref_lla = ecef_to_lla(reference)
    lat, lon = math.radians(ref_lla.lat), math.radians(ref_lla.lon)
    dx, dy, dz = target.x - reference.x, target.y - reference.y, target.z - reference.z
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)
    south = sin_lat * cos_lon * dx + sin_lat * sin_lon * dy - cos_lat * dz
    east = -sin_lon * dx + cos_lon * dy
    zenith = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz
    return south, east, zenith


def compute_look_angles(station: GroundStation, sat_ecef: ECEF) -> LookAngles:
    delta = sat_ecef - station.ecef
    range_m = delta.magnitude
    if range_m <= 0.0:
        raise ValueError("satellite and station positions coincide")
    south, east, zenith = ecef_to_sez(sat_ecef, station.ecef)
    azimuth = math.atan2(east, -south) % (2.0 * math.pi)
    elevation = math.atan2(zenith, math.hypot(south, east))
    return LookAngles(math.degrees(azimuth), math.degrees(elevation), range_m)


def doppler_shift(station: GroundStation, sat_ecef: ECEF, sat_vel: tuple[float, float, float]) -> float:
    if len(sat_vel) != 3:
        raise ValueError("sat_vel must contain three ECEF components")
    velocity = tuple(_finite(f"sat_vel[{index}]", value) for index, value in enumerate(sat_vel))
    delta = sat_ecef - station.ecef
    distance = delta.magnitude
    if distance <= 0.0:
        return 0.0
    line_of_sight = (delta.x / distance, delta.y / distance, delta.z / distance)
    radial_velocity = sum(velocity[index] * line_of_sight[index] for index in range(3))
    return -station.frequency_hz * radial_velocity / C


def predict_pass(
    station: GroundStation,
    sat_positions: list[tuple[ECEF, tuple[float, float, float], float]],
    min_elev: float | None = None,
) -> list[dict]:
    mask = station.min_elevation if min_elev is None else _finite("min_elev", min_elev)
    pass_data: list[dict] = []
    acquired = False
    for sat_ecef, sat_vel, timestamp in sat_positions:
        angles = compute_look_angles(station, sat_ecef)
        if angles.elevation >= mask:
            pass_data.append({
                "time": _finite("time", timestamp),
                "azimuth": round(angles.azimuth, 3),
                "elevation": round(angles.elevation, 3),
                "range_km": round(angles.range_m / 1000.0, 3),
                "doppler_hz": round(doppler_shift(station, sat_ecef, sat_vel), 3),
            })
            acquired = True
        elif acquired:
            break
    return pass_data
