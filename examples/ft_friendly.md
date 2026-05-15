# FT-friendly pattern comparison

| Pattern                    | File                 | GIL    | FT     | delta  |
|----------------------------|----------------------|--------|--------|--------|
| Embarrassingly parallel    | embarrassingly_parallel.py | 4.17s  | 0.74s  | -82.3% |
| Async + CPU offload        | async_cpu_offload.py | 4.12s  | 0.79s  | -80.8% |
| Sharded accumulators       | counter_sharded.py   | 0.02s  | 0.01s  | -50.0% |
| Coarse-grained locking     | counter_coarse.py    | 0.08s  | 0.02s  | -75.0% |
| Read-mostly shared state   | cache_readmostly.py  | 7.72s  | 1.23s  | -84.1% |
| Pipeline parallelism (CSP) | counter_csp_work.py  | 34.79s | 19.97s | -42.6% |
