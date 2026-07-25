# Issue Contract — `spacex-ground-network`

## Pain
Must select ground stations by elevation/SNR/capacity to meet bandwidth need.

## Claim
Planner meets need_mbps when capacity exists; fails when short.

## Proof
```bash
python3 job-app/helix/proofs/proof_ground.py
```

## Done when
Proof exits 0. Architecture (strand/integrity/helix) is **not** a substitute for this proof.

## Anti-claim
Not a real antenna network.
