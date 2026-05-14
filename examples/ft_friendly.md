# FT-friendly pattern comparison

| Pattern                    | File                 | GIL    | FT     | delta  |
|----------------------------|----------------------|--------|--------|--------|
| Embarrassingly parallel    | cpu_parallel.py      | 4.08s  | 0.78s  | -80.9% |
| Async + CPU offload        | async_cpu_offload.py | 4.08s  | 0.78s  | -80.9% |
| Sharded accumulators       | counter_sharded.py   | 0.02s  | 0.01s  | -50.0% |
| Coarse-grained locking     | counter_coarse.py    | 0.08s  | 0.02s  | -75.0% |
| Read-mostly shared state   | cache_readmostly.py  | 7.81s  | 1.11s  | -85.8% |
| Pipeline parallelism (CSP) | counter_csp_work.py  | 59.60s | 19.81s | -66.8% |
