# HELIX Architecture — spacex-ground-network

## Double Helix Pattern

**Alpha (What)** — Pure physics models, stateless computation
- antenna_tracker

**Omega (How)** — Controllers, orchestration, stateful management  
- network_manager,predictive_handoff

## Design Principles

- Zero external dependencies (stdlib only)
- Stateless alpha, stateful omega
- SHA-256 file integrity verification
- Shadow watchdog daemon monitoring
- Mastermind sidecar coordination

## Data Flow

```
Alpha Models → Omega Controllers → Mastermind Sidecar → Shadow Infrastructure
```
