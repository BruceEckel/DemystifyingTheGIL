# FT-friendly pattern comparison

| Pattern                    | File                         | GIL    | FT     | Speedup |
|----------------------------|------------------------------|--------|--------|---------|
| Embarrassingly parallel    | `embarrassingly_parallel.py` | 4.30s  | 0.77s  | 5.58x   |
| Async + CPU offload        | `async_cpu_offload.py`       | 4.37s  | 0.87s  | 5.02x   |
| Sharded accumulators       | `counter_sharded.py`         | 0.02s  | 0.01s  | 2.00x   |
| Coarse-grained locking     | `counter_coarse.py`          | 0.08s  | 0.02s  | 4.00x   |
| Read-mostly shared state   | `cache_readmostly.py`        | 8.01s  | 1.19s  | 6.73x   |
| Pipeline parallelism (CSP) | `counter_csp_work.py`        | 35.93s | 16.44s | 2.19x   |
