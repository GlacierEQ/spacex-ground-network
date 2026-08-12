# Ground Network — predictive contact and handoff reference

> Independent GlacierEQ portfolio implementation for ground-station geometry, link-budget ranking, and predictive handoff mechanics. This is not SpaceX software, employment work, operational ground infrastructure, or evidence of SpaceX adoption.

## What is implemented

The repository contains a Python reference stack for four concrete mechanisms:

- `src/alpha/antenna_tracker.py` — WGS84-style LLA/ECEF transforms, azimuth/elevation/range calculation, line-of-sight Doppler estimation, and pass visibility extraction from supplied satellite states.
- `src/omega/network_manager.py` — ground-station registration, simplified RF link-budget calculation, station selection by link margin, handoff logging, and network-health summaries.
- `src/omega/predictive_handoff.py` — a simplified J2/mean-motion orbital predictor used to compute future look angles and pre-positioning recommendations before an expected pass.
- `src/promotion_authority.py` — local proof-bound promotion semantics with explicit receipt/integrity boundaries.

`src/ground_net.py` remains a small compatibility/reference surface. The implemented runtime is Python; there is no Go antenna-tracker implementation in the current repository.

## Current verification boundary

Canonical source before this projection repair: `d5b65ecfb8d0fdd24ba033b2e4737346179c4a7e`.

Repository-native CI run `31472449875` executed against that exact revision through immutable reusable verification authority `public-actions-runner-host@a6085dae73bb80e91b845fd4a0d2f73a9c6b985a` and passed:

- critical Ruff correctness checks;
- Python compileall;
- **22/22 tests**, including adversarial and promotion-authority coverage;
- read-only GitHub token authority;
- checkout without persisted credentials;
- bounded verification artifact `9093856530`, SHA-256 `3c4ead4a9bec56e5235a145fbe3bdeb0ac2544c1919789e48173b08e52146f21`.

That proof belongs only to `d5b65ec...`. This projection/metadata repair changes source state and must earn a new exact-head repository-native receipt before the repaired revision is promoted.

## Architecture

```text
supplied station + satellite state
        │
        ├── antenna_tracker.py
        │     LLA ⇄ ECEF
        │     look angles / range
        │     Doppler estimate
        │     visibility samples
        │
        ├── network_manager.py
        │     simplified link budget
        │     viable-station ranking
        │     handoff log
        │     network health
        │
        └── predictive_handoff.py
              simplified orbital prediction
              future azimuth/elevation
              pre-position recommendation
              modeled handoff state
```

## Engineering limits

This is a deterministic engineering reference, not an operational ground network. In particular:

- orbital propagation is simplified and is not claimed as flight-dynamics-grade ephemeris propagation;
- the link budget uses fixed/reference parameters rather than calibrated production RF hardware data;
- `execute_handoff()` changes local model state only; it does not command antennas, radios, spacecraft, or mission systems;
- the modeled `acquisition_time_ms: 0` is a simulation/state-contract value, not a measured latency result;
- no production availability, geographic scale, constellation-scale throughput, latency SLO, or continuous-contact claim is established.

## Explicit nonclaims

Earlier README language exceeded the implemented repository. The following are **not** current capabilities and must not be inferred:

- no Go `antenna_tracker.go` implementation;
- no live MCP `station_status` or `coverage_check` service;
- no Mastermind/APEX Highway sidecar integration;
- no ML interference predictor or adaptive-modulation model;
- no production telemetry decoder, command uplink, antenna actuator, or automatic failover service;
- no measured 2–5 second acquisition-time saving;
- no verified 6,000-satellite or planetary-scale operation;
- no SpaceX affiliation, endorsement, adoption, proprietary access, or production deployment.

## Verification

The repository-owned gate is `scripts/ci/verify.sh` and is executed by the pinned reusable workflow in `.github/workflows/ci.yml`.

```bash
bash scripts/ci/verify.sh
```

The verification suite includes deterministic core/network checks, dedicated adversarial tests, and proof-bound promotion-authority tests. Passing tests establish repository-native reference behavior only; they do not grant operational authority.

## Estate role

Current intended role: **active specialist component for bounded ground-contact geometry and predictive handoff reference mechanics**.

Its distinct value versus adjacent SpaceX-family components is the combination of station-centric geometry, simplified RF link-margin ranking, and pre-positioning/handoff state. Final canonical-family ownership remains subject to direct family comparison; the repository name alone is not proof of uniqueness.
