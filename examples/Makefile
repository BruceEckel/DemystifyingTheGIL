GIL   = uv run --python 3.14+gil
NOGIL = uv run --python 3.14t

EXAMPLES = counter_race.py counter_lock.py two_counters.py context_switch.py \
           surprise.py no_surprise.py stats_race.py connection_pool.py refcount_race.py \
           cpu_parallel.py

.PHONY: all gil nogil overhead help $(EXAMPLES)

.DEFAULT_GOAL := help

help:
	@echo "Usage:"
	@echo "  make gil          -- run all examples with the GIL"
	@echo "  make nogil        -- run all examples without the GIL"
	@echo "  make all          -- run both"
	@echo "  make overhead     -- compare single-threaded perf across builds"
	@echo "  make <script.py>  -- run one example with GIL then no GIL (no .\ prefix)"

all: gil nogil

gil:
	@echo "=== counter_race.py ==="
	$(GIL) counter_race.py
	@echo "=== counter_lock.py ==="
	$(GIL) counter_lock.py
	@echo "=== two_counters.py ==="
	$(GIL) two_counters.py
	@echo "=== context_switch.py ==="
	$(GIL) context_switch.py
	@echo "=== surprise.py ==="
	$(GIL) surprise.py
	@echo "=== no_surprise.py ==="
	$(GIL) no_surprise.py
	@echo "=== stats_race.py ==="
	$(GIL) stats_race.py
	@echo "=== connection_pool.py ==="
	$(GIL) connection_pool.py
	@echo "=== refcount_race.py ==="
	$(GIL) refcount_race.py
	@echo "=== cpu_parallel.py ==="
	$(GIL) cpu_parallel.py

nogil:
	@echo "=== counter_race.py ==="
	$(NOGIL) counter_race.py
	@echo "=== counter_lock.py ==="
	$(NOGIL) counter_lock.py
	@echo "=== two_counters.py ==="
	$(NOGIL) two_counters.py
	@echo "=== context_switch.py ==="
	$(NOGIL) context_switch.py
	@echo "=== surprise.py ==="
	$(NOGIL) surprise.py
	@echo "=== no_surprise.py ==="
	$(NOGIL) no_surprise.py
	@echo "=== stats_race.py ==="
	$(NOGIL) stats_race.py
	@echo "=== connection_pool.py ==="
	$(NOGIL) connection_pool.py
	@echo "=== refcount_race.py ==="
	$(NOGIL) refcount_race.py
	@echo "=== cpu_parallel.py ==="
	$(NOGIL) cpu_parallel.py

overhead:
	uv run python compare_overhead.py

$(EXAMPLES):
	$(GIL) $@
	$(NOGIL) $@
