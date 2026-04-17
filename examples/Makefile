GIL   = uv run --python 3.14+gil
NOGIL = uv run --python 3.14t

EXAMPLES = unsafe.py safe.py two_variable.py context_switch.py \
           surprise.py no_surprise.py stats.py connection_pool.py refcount_race.py

.PHONY: all gil nogil help $(EXAMPLES)

.DEFAULT_GOAL := help

help:
	@echo "Usage:"
	@echo "  make gil          -- run all examples with the GIL"
	@echo "  make nogil        -- run all examples without the GIL"
	@echo "  make all          -- run both"
	@echo "  make <script.py>  -- run one example with GIL then no GIL (no .\ prefix)"

all: gil nogil

gil:
	@echo "=== unsafe.py ==="
	$(GIL) unsafe.py
	@echo "=== safe.py ==="
	$(GIL) safe.py
	@echo "=== two_variable.py ==="
	$(GIL) two_variable.py
	@echo "=== context_switch.py ==="
	$(GIL) context_switch.py
	@echo "=== surprise.py ==="
	$(GIL) surprise.py
	@echo "=== no_surprise.py ==="
	$(GIL) no_surprise.py
	@echo "=== stats.py ==="
	$(GIL) stats.py
	@echo "=== connection_pool.py ==="
	$(GIL) connection_pool.py
	@echo "=== refcount_race.py ==="
	$(GIL) refcount_race.py

nogil:
	@echo "=== unsafe.py ==="
	$(NOGIL) unsafe.py
	@echo "=== safe.py ==="
	$(NOGIL) safe.py
	@echo "=== two_variable.py ==="
	$(NOGIL) two_variable.py
	@echo "=== context_switch.py ==="
	$(NOGIL) context_switch.py
	@echo "=== surprise.py ==="
	$(NOGIL) surprise.py
	@echo "=== no_surprise.py ==="
	$(NOGIL) no_surprise.py
	@echo "=== stats.py ==="
	$(NOGIL) stats.py
	@echo "=== connection_pool.py ==="
	$(NOGIL) connection_pool.py
	@echo "=== refcount_race.py ==="
	$(NOGIL) refcount_race.py

$(EXAMPLES):
	$(GIL) $@
	$(NOGIL) $@
