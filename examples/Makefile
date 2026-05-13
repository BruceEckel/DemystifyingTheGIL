GIL   = uv run --python 3.14+gil
NOGIL = uv run --python 3.14t

EXAMPLES = concurrency_is_easy.py the_camels_nose.py cpu_parallel.py counter_sharded.py \
           counter_coarse.py cache_readmostly.py \
           counter_race.py counter_lock.py counter_actor.py counter_csp.py two_counters.py \
           context_switch.py surprise.py no_surprise.py stats_race.py connection_pool.py \
           refcount_race.py dis_increment.py opmap_contents.py async_fetch.py mp_pool.py \
           process_pool_executor.py

GIL_TARGETS   = $(addprefix gil-,$(EXAMPLES))
NOGIL_TARGETS = $(addprefix nogil-,$(EXAMPLES))
DOT_EXAMPLES  = $(addprefix .\,$(EXAMPLES))

# When `gil` or `nogil` appears alongside a script on the command line,
# treat it as a mode selector instead of a target that runs everything.
MODE_FLAG       = $(filter gil nogil,$(MAKECMDGOALS))
SCRIPT_GOAL     = $(filter $(EXAMPLES) $(DOT_EXAMPLES),$(MAKECMDGOALS))
MODE_AND_SCRIPT = $(if $(MODE_FLAG),$(SCRIPT_GOAL))

.PHONY: all gil nogil overhead FTFriendly help list present $(EXAMPLES)

.DEFAULT_GOAL := help

help:
	@echo "Usage:"
	@echo "  make gil                  -- run all examples with the GIL"
	@echo "  make nogil                -- run all examples without the GIL"
	@echo "  make all                  -- run both"
	@echo "  make overhead             -- compare single-threaded performance across builds"
	@echo "  make FTFriendly           -- compare FT-friendly patterns across builds"
	@echo "  make present              -- launch the Slidev slide preview"
	@echo "  make list                 -- list all <script.py> options"
	@echo "  make <script.py>          -- run one example with GIL then no GIL (.\ prefix ok)"
	@echo "  make gil <script.py>      -- run one example with GIL only"
	@echo "  make nogil <script.py>    -- run one example without the GIL only"

all: gil nogil

gil-%:
	@echo "=== $* ==="
	$(GIL) $*

nogil-%:
	@echo "=== $* ==="
	$(NOGIL) $*

overhead:
	uv run python compare_overhead.py

FTFriendly:
	uv run python ft_friendly.py

list:
	@$(foreach e,$(EXAMPLES),echo $(e);)

present:
	npm --prefix ../presentation run dev -- DemystifyingTheGIL.md

ifneq ($(MODE_AND_SCRIPT),)
# Mode flag plus script: flag selects the build, script runs once in that mode.
gil: ; @:
nogil: ; @:
ifneq ($(filter nogil,$(MODE_FLAG)),)
$(EXAMPLES):
	$(NOGIL) $@
else
$(EXAMPLES):
	$(GIL) $@
endif
else
gil: $(GIL_TARGETS)
nogil: $(NOGIL_TARGETS)
$(EXAMPLES):
	$(GIL) $@
	$(NOGIL) $@
endif

# Accept .\<name>.py from PowerShell tab-completion by forwarding to the plain target.
define dot_rule
.\$(1): $(1) ;
endef
$(foreach e,$(EXAMPLES),$(eval $(call dot_rule,$(e))))
