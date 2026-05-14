
---


# Why It "Works" With the GIL

- The GIL is released only at predictable points:
  - The "check interval": every 5 ms (Python 3.11+)
  - Backward jumps and function calls only (Python 3.11+)
- Those 3 bytecodes are short enough that the GIL often isn't released between them
- But this is **not guaranteed** — it's timing luck
- Even with the GIL, long enough critical sections *can* be interrupted

---

# You Don't Write Most of Your Code

- Most libraries were written under the GIL assumption
- Most library authors didn't know they needed to think about thread safety
- The GIL was their lock -- silent & invisible, without their knowledge


---

# Why This Is Hard to Find

- Race conditions are **non-deterministic** — the bug may appear 1 in 10,000 runs
- Your test suite runs sequentially or with low concurrency → green CI
- The bug surfaces under production load, specific hardware, or after an OS scheduler change
- Python 3.14t makes races *more likely* but still not certain
- Luckily: 3.14t is a correctness checker you can run today

---

# What You Should Do Now

1. **Audit shared mutable state** — anything touched by more than one thread
2. **Run your test suite under 3.14t** — it will expose latent races that the GIL was hiding
3. **Add explicit locks** — `threading.Lock`, `threading.RLock`, `queue.Queue`
4. **Prefer immutable data** — objects created once and never mutated are safe
5. **Check your dependencies** — file issues against libraries that don't declare thread safety

---

# The Payoff

Why bother? Because without the GIL:

- CPU-bound threads actually run in parallel on multiple cores
- `threading` becomes a genuine tool for parallelism, not just I/O concurrency
- Python can compete with Go and Java for multi-core throughput
- The ecosystem has 30 years of battle-tested concurrency primitives to use
- Libraries that do the work correctly will be faster and more scalable

---

# The Rule

> If two threads touch the same data and at least one of them writes,
> you need a lock — **GIL or not**.

- This has always been true
- The GIL made it optional in CPython — that era is ending
- Code that follows this rule works correctly on every Python implementation, today and tomorrow
