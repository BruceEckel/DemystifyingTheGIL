GIL   = uv run --python 3.14+gil
NOGIL = uv run --python 3.14t

EXAMPLES = counter_race.py counter_lock.py counter_actor.py two_counters.py context_switch.py \
           surprise.py no_surprise.py stats_race.py connection_pool.py refcount_race.py \
           cpu_parallel.py dis_increment.py opmap_contents.py async_fetch.py \
           mp_pool.py process_pool_executor.py

GIL_TARGETS   = $(addprefix gil-,$(EXAMPLES))
NOGIL_TARGETS = $(addprefix nogil-,$(EXAMPLES))

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

gil: $(GIL_TARGETS)
nogil: $(NOGIL_TARGETS)

gil-%:
	@echo "=== $* ==="
	$(GIL) $*

nogil-%:
	@echo "=== $* ==="
	$(NOGIL) $*

overhead:
	uv run python compare_overhead.py

$(EXAMPLES):
	$(GIL) $@
	$(NOGIL) $@
