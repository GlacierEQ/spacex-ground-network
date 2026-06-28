# SpaceX Ground Network

Ground station antenna tracking and network management for satellite operations.

## Architecture

**Double Helix (Alpha + Omega)**

- **Alpha** (`src/alpha/antenna_tracker.py`): Coordinate transforms (LLA ↔ ECEF), look angle computation, Doppler prediction.
- **Omega** (`src/omega/network_manager.py`): Station selection, link budget analysis, handoff management.

## Features

- WGS-84 ellipsoid coordinate transforms
- Azimuth/elevation/range computation
- Doppler shift prediction
- Link budget with CNR and margin
- Automated station handoff
- Zero external dependencies
