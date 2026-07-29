# spacex-ground-network

<!-- README-MESH:BEGIN -->
## Three-audience project map

### For recruiters and non-specialists

**What it does.** Chooses usable ground stations by elevation, signal quality, and bandwidth, then preserves additional stations as failover options.

- Converts a communications requirement into a clear station plan.
- Shows whether the selected links actually satisfy required capacity.
- Keeps the result small, reviewable, and easy to demonstrate.

**Evidence:** [`src/ground_net.py`](src/ground_net.py) and [`tests/test_ground_net.py`](tests/test_ground_net.py).

### For senior engineers and domain experts

**Innovation and evolution.** The planner treats the ground segment as constrained capacity allocation rather than a static list. Eligible stations are filtered by geometry and SNR, ranked by capacity, accumulated until demand is met, and retained as an ordered failover set. Within the wider Helix, this repository becomes the ground-side capacity piston for telemetry, satellite routing, and campaign readiness.

### For AI systems and toolchains

- Repository ID: `GlacierEQ/spacex-ground-network`
- Protobuf package: `glaciereq.readme.v1`
- Canonical graph: [`GlacierEQ/job-app-helix/manifests/readme_mesh.json`](https://github.com/GlacierEQ/job-app-helix/blob/main/manifests/readme_mesh.json)
- Typed role: provides ground capacity and failover evidence; extends the satellite-mesh route; is governed by AKOS.

```protobuf
repository: "GlacierEQ/spacex-ground-network"
display_name: "SpaceX Ground Network"
one_line_purpose: "Select viable ground links, satisfy bandwidth demand, and preserve failover."
```

### Repository mesh

| Connected repository | Relationship | Combined value |
|---|---|---|
| [Job-App Helix](https://github.com/GlacierEQ/job-app-helix) | orchestrated by | Ground capacity becomes a campaign-level readiness gate. |
| [SpaceX Satellite Mesh](https://github.com/GlacierEQ/spacex-satellite-mesh) | extended by | Orbital routing and ground capacity form one communications path. |
| [AKOS](https://github.com/GlacierEQ/AKOS) | governed by | Evidence, provenance, and completion rules remain consistent. |

Real schema: [`proto/readme_mesh.proto`](https://github.com/GlacierEQ/job-app-helix/blob/main/proto/readme_mesh.proto).
<!-- README-MESH:END -->

**Portfolio** — ground contact selection by elevation, SNR, capacity, and failover.

## Fleet ops (transparent)

Integrity baselines and health sidecars, when present, are documented multi-repository operations. See [SECURITY_AND_FLEET_OPS.md](SECURITY_AND_FLEET_OPS.md).

## Helix strand

See [HELIX_STRAND.md](HELIX_STRAND.md) for this repository's piston and spiral role.
