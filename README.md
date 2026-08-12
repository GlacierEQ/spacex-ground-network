# Ground Network Planner

**Deterministic WGS-84 tracking geometry, RF link-budget screening, station selection, handoff simulation, and a native Go scheduling kernel.**

This is an independent GlacierEQ portfolio system. It is not affiliated with SpaceX and provides no RF transmission, command uplink, antenna actuation, spacecraft control, or operational network authority.

## What now works

- WGS-84 LLA ↔ ECEF coordinate conversion with high-latitude round-trip tests;
- azimuth/elevation/range look-angle computation;
- ECEF-frame line-of-sight Doppler estimation;
- validated free-space link budget with received power, noise power, C/N and margin;
- station eligibility based on elevation mask, RF margin, health and load ceiling;
- load-aware selection and handoff hysteresis to avoid unnecessary station chatter;
- deterministic contact-series screening and handoff history;
- J2 secular-rate + Kepler predictive position model with Earth-rotation conversion to ECEF;
- review-only pre-position angles and simulated handoffs;
- executable `ground-network` JSON planning CLI;
- native Go station-selection kernel with duplicate validation, health/load/link screening and race-tested unit tests.

## Run it

```bash
python -m pip install -e . pytest
pytest -q
ground-network demo

go test -race ./...
go run ./cmd/groundnet
```

## Architecture

```text
Satellite ECEF state + velocity
              |
              v
     WGS-84 tracking geometry
       |               |
       |               +--> Doppler
       v
     Look angles ---> RF link budget
                          |
Station health + load ----+
                          v
                 selection / hysteresis
                          |
                          +--> contact events
                          +--> handoff history

Orbital elements --> J2/Kepler predictor --> ECI->ECEF --> pre-position review

Computed station metrics --> Go selection kernel --> deterministic routing choice
```

## Core surfaces

| Surface | Function |
|---|---|
| `src/alpha/antenna_tracker.py` | WGS-84 geometry, look angles, Doppler and visibility samples |
| `src/omega/network_manager.py` | link budget, viability, health/load-aware selection and hysteresis |
| `src/omega/predictive_handoff.py` | review-grade orbit prediction, Earth rotation and pre-position/handoff simulation |
| `src/ground_network.py` | JSON planning engine and CLI |
| `cmd/groundnet` | native Go deterministic station-selection kernel |
| `tests/test_crystallized_function.py` | geometry, RF validity, failover, load, hysteresis, orbit and CLI behavior |

## Corrected claims

The previous README named `src/ground_network.py` and `src/antenna_tracker.go`, neither of which existed. It also claimed real-time antenna pointing, automatic fault-tolerant command handoff, MCP tooling and APEX integration that were not represented by executable repository surfaces.

The crystallized repository now provides the Python entrypoint it advertised and a real Go boundary where Go is technically useful: a small native, race-tested station-selection kernel. It does **not** manufacture a fake Go antenna controller just to satisfy a language badge.

The prior network manager also ignored `load_percent` during station selection and did not require a viable RF margin. Those are now part of the actual selection contract.

## Predictive-model limits

The predictive handoff model is a local engineering approximation using Kepler motion plus secular J2 rates and Earth rotation. It is not SGP4, an operational ephemeris service, or evidence of zero-millisecond acquisition. `execute_handoff` remains only as a compatibility alias for a **simulated** state transition.

## Machine contract

```yaml
schema: glaciereq.readme.v1
repository: GlacierEQ/spacex-ground-network
purpose: deterministic ground-station tracking and network-planning simulation
state: FUNCTIONAL_CANDIDATE
languages:
  python:
    role: geometry, RF analysis, network selection, predictive handoff, CLI
  go:
    role: native deterministic station-selection kernel
promotion_requires:
  - Python 3.11 functional proof
  - Python 3.12 functional proof
  - Python 3.13 functional proof
  - Go vet
  - Go race-tested unit proof
  - Go executable smoke
  - required-functional-proof
nonclaims:
  - no SpaceX affiliation
  - no RF transmit authority
  - no spacecraft command uplink
  - no antenna hardware actuation
  - no live MCP or APEX integration
  - no operational acquisition-time guarantee
```

**The network is judged by geometry, RF viability, deterministic selection and executable proof, not by badges or orchestration paperwork.**
