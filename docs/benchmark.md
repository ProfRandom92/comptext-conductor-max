# Benchmark

## Scope
The benchmark is a deterministic **synthetic** stress fixture. It contains many source files, a large Conductor specification and plan, a working-tree Git diff, generated/lock data, a binary change, and a 6,500-line test log. It is intended to test the mechanism, not predict every real repository.

Seed: `20260807`  
Fixture SHA-256: `60e3a95992e3dd4786f8e858991bf8ca3cedff8831ae05ca93c42b2937c38421`  
Token metric: `estimated_tokens`

## Final measured result
| Mode | Raw bytes | Returned bytes | Raw estimated tokens | Returned estimated tokens | Token reduction | Missing required facts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| NAIVE | 986,077 | 986,077 | 246,520 | 246,520 | 0.00% | 0 |
| SAFE | 986,077 | 13,910 | 246,520 | 3,478 | 98.59% | 0 |
| BALANCED | 986,077 | 13,910 | 246,520 | 3,478 | 98.59% | 0 |
| MAX | 986,077 | 13,910 | 246,520 | 3,478 | 98.59% | 0 |

The gate passes when BALANCED or MAX returns at least 50% less model-delivered context with every required fixture fact retained. This run passed. The equality of SAFE/BALANCED/MAX returned sizes here means the relevant set fit below all three ceilings; it does not mean profile behavior is identical when relevant context grows.

## Reproduction
```bash
ct-conductor benchmark --output benchmarks/results/latest.json --seed 20260807
```

`benchmarks/results/latest.json` is the source of truth for documented measurements. Latency is an observed local-run value and may vary between machines/runs. No historical savings claim from another CompText or third-party project is treated as evidence for this benchmark.
