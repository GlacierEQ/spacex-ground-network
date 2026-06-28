"""Ground station antenna tracking — ECEF position, look angles, Doppler.

Computes azimuth/elevation from ground station to satellite in real-time.
Handles coordinate transforms (LLA → ECEF) and Doppler shift prediction.
Pure math, zero external dependencies.
"""

import math
from dataclasses import dataclass

R_EARTH = 6378137.0
F = 1 / 298.257223563
E2 = 2 * F - F ** 2
C = 299792458.0
OMEGA_E = 7.2921159e-5


@dataclass
class LLA:
    lat: float
    lon: float
    alt: float


@dataclass
class ECEF:
    x: float
    y: float
    z: float

    def __sub__(self, other: "ECEF") -> "ECEF":
        return ECEF(self.x - other.x, self.y - other.y, self.z - other.z)

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2 + self.z ** 2)


@dataclass
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
    _ecef: ECEF = None

    def __post_init__(self):
        self._ecef = lla_to_ecef(self.location)

    @property
    def ecef(self) -> ECEF:
        return self._ecef


def lla_to_ecef(lla: LLA) -> ECEF:
    lat_rad = math.radians(lla.lat)
    lon_rad = math.radians(lla.lon)

    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    sin_lon = math.sin(lon_rad)
    cos_lon = math.cos(lon_rad)

    N = R_EARTH / math.sqrt(1 - E2 * sin_lat ** 2)

    x = (N + lla.alt) * cos_lat * cos_lon
    y = (N + lla.alt) * cos_lat * sin_lon
    z = (N * (1 - E2) + lla.alt) * sin_lat

    return ECEF(x, y, z)


def ecef_to_lla(ecef: ECEF) -> LLA:
    x, y, z = ecef.x, ecef.y, ecef.z

    lon = math.atan2(y, x)
    p = math.sqrt(x ** 2 + y ** 2)
    lat = math.atan2(z, p * (1 - E2))

    for _ in range(10):
        sin_lat = math.sin(lat)
        N = R_EARTH / math.sqrt(1 - E2 * sin_lat ** 2)
        lat = math.atan2(z + E2 * N * sin_lat, p)

    N = R_EARTH / math.sqrt(1 - E2 * math.sin(lat) ** 2)
    alt = p / math.cos(lat) - N

    return LLA(math.degrees(lat), math.degrees(lon), alt)


def ecef_to_sez(target: ECEF, reference: ECEF) -> tuple[float, float, float]:
    """ECEF to South-East-Zenith at reference point."""
    dx = target.x - reference.x
    dy = target.y - reference.y
    dz = target.z - reference.z

    lat_rad = math.atan2(reference.z, math.sqrt(reference.x ** 2 + reference.y ** 2))
    lon_rad = math.atan2(reference.y, reference.x)

    cos_lat, sin_lat = math.cos(lat_rad), math.sin(lat_rad)
    cos_lon, sin_lon = math.cos(lon_rad), math.sin(lon_rad)

    south = -cos_lon * sin_lat * dx - sin_lon * sin_lat * dy + cos_lat * dz
    east = -sin_lon * dx + cos_lon * dy
    zenith = cos_lon * cos_lat * dx + sin_lon * cos_lat * dy + sin_lat * dz

    return south, east, zenith


def compute_look_angles(station: GroundStation, sat_ecef: ECEF) -> LookAngles:
    """Azimuth, elevation, range from ground station to satellite."""
    dx = sat_ecef - station.ecef
    range_m = dx.magnitude

    south, east, zenith = ecef_to_sez(sat_ecef, station.ecef)

    azimuth = math.atan2(east, -south)
    if azimuth < 0:
        azimuth += 2 * math.pi

    elevation = math.atan2(zenith, math.sqrt(south ** 2 + east ** 2))

    return LookAngles(
        azimuth=math.degrees(azimuth),
        elevation=math.degrees(elevation),
        range_m=range_m,
    )


def doppler_shift(
    station: GroundStation, sat_ecef: ECEF, sat_vel: tuple[float, float, float]
) -> float:
    """Compute Doppler shift for satellite pass."""
    dx = sat_ecef - station.ecef
    r = dx.magnitude
    if r == 0:
        return 0.0

    rx, ry, rz = dx.x / r, dx.y / r, dx.z / r
    v_radial = sat_vel[0] * rx + sat_vel[1] * ry + sat_vel[2] * rz

    return -station.frequency_hz * v_radial / C


def predict_pass(
    station: GroundStation,
    sat_positions: list[tuple[ECEF, tuple[float, float, float], float]],
    min_elev: float = None,
) -> list[dict]:
    """Predict visibility pass from sequence of satellite positions."""
    min_elev = min_elev or station.min_elevation
    pass_data = []
    visible = False

    for sat_ecef, sat_vel, t in sat_positions:
        angles = compute_look_angles(station, sat_ecef)

        if angles.elevation >= min_elev:
            dop = doppler_shift(station, sat_ecef, sat_vel)
            entry = {
                "time": t,
                "azimuth": round(angles.azimuth, 2),
                "elevation": round(angles.elevation, 2),
                "range_km": round(angles.range_m / 1000, 1),
                "doppler_hz": round(dop, 0),
            }
            pass_data.append(entry)
            visible = True
        elif visible:
            break

    return pass_data
