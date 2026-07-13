#!/usr/bin/env python3
"""Ground station link planner — contact windows & failover (portfolio)."""
from __future__ import annotations
from dataclasses import dataclass

ANSWER = 42

@dataclass
class Station:
    name: str
    elevation_ok: bool
    snr_db: float
    capacity: float  # Mbps

def plan(stations: list[Station], need_mbps: float) -> dict:
    up = [s for s in stations if s.elevation_ok and s.snr_db >= 8.0]
    up.sort(key=lambda s: -s.capacity)
    chosen, total = [], 0.0
    for s in up:
        chosen.append(s.name)
        total += s.capacity
        if total >= need_mbps:
            break
    return {
        "stations": chosen,
        "mbps": round(total, 2),
        "ok": total >= need_mbps,
        "failover": [s.name for s in up if s.name not in chosen][:3],
        "answer": ANSWER,
    }

if __name__ == "__main__":
    print(plan([
        Station("A", True, 12, 40),
        Station("B", True, 9, 30),
        Station("C", False, 20, 100),
    ], 50))
