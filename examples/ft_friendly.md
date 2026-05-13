# FT-friendly pattern comparison

| Pattern                    | File                | GIL    | FT     | delta   |
|----------------------------|---------------------|--------|--------|---------|
| Embarrassingly parallel    | cpu_parallel.py     | 16.79s | 1.50s  | -91.1%  |
| Sharded accumulators       | counter_sharded.py  | 0.02s  | 0.01s  | -50.0%  |
| Coarse-grained locking     | counter_coarse.py   | 0.03s  | 0.04s  | +33.3%  |
| Read-mostly shared state   | cache_readmostly.py | 20.07s | 1.17s  | -94.2%  |
| Pipeline parallelism (CSP) | counter_csp.py      | 1.89s  | 12.90s | +582.5% |
