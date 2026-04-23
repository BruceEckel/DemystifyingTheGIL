# The GIL and Context Switching

How many opcodes does Python have?
The count depends on how you measure and which Python version you're running.
**Base opcodes** (the ones you see in `dis` output) number roughly **100–130**
in Python 3.13/3.14. You can check exactly:

```python
# opmap_contents.py
import opcode

print(f"opmap entries: {len(opcode.opmap)}")  # "public" opcodes visible in dis output
print(f"opname entries: {len(opcode.opname)}")  # larger: also includes <N> reserved slots,
                                                 # INSTRUMENTED_* debugger opcodes, and
                                                 # pseudo-instructions used during compilation

for num, name in enumerate(opcode.opname):
    print(f"  {num:3d}  {name}")
```

On top of that, Python 3.11+ added **specialized/adaptive opcodes**: internal
variants like `LOAD_FAST_CHECK` and `BINARY_OP_ADD_INT` that the interpreter
substitutes at runtime for frequently-executed code paths. These add another
~50–60, bringing the total to roughly 180–220 entries in the opcode table.

## Why this matters for the GIL demo

The race condition in `counter += 1` comes from the fact that it is **not
atomic**. You can see the opcodes it compiles to with `dis`:

```python
import dis

def increment():
    counter += 1

dis.dis(increment)
```

Output:
```
  4           RESUME          0

  5           LOAD_FAST_CHECK  0 (counter)
              LOAD_SMALL_INT   1
              BINARY_OP       13 (+=)
              STORE_FAST       0 (counter)
```

The columns are: source line number, byte offset, opcode name, numeric argument,
and a human-readable annotation of the argument in parentheses.

That's three separate opcodes doing the work:

| Opcode        | What it does                          |
|---------------|---------------------------------------|
| `LOAD_FAST`   | Push `counter`'s value onto the stack |
| `BINARY_OP`   | Compute `counter + 1`                 |
| `STORE_FAST`  | Write the result back to `counter`    |

The GIL can release between any of these. If two threads both execute `LOAD`
before either executes `STORE`, they both see the same starting value and one
increment is silently lost.


## The old model: 100 opcodes (Python 1.0 – 3.1)

For most of Python's history, the GIL released every **100 opcodes**,
controlled by `sys.getcheckinterval()`. This was a round number chosen for
simplicity, not calibrated to any particular latency target.

On 1990s hardware (millions of simple operations per second), 100 opcodes may
have *accidentally* approximated a few milliseconds. But as hardware got faster,
100 opcodes shrank to microseconds, and by the time Python 3.2 shipped in 2011,
threads were fighting over the GIL far more often than intended. The
coordination overhead from constant acquire/release cycles hurt performance
even on single-threaded programs, since the check fired regardless of how
many threads were running.

## The current model: 5ms (Python 3.2+)

Python 3.2 replaced the opcode counter with a **time-based mechanism**,
defaulting to 5ms (`sys.getswitchinterval()`). A background watchdog thread sets
an `eval_breaker` flag every 5ms; the running thread checks that flag and yields
the GIL when it fires.

In a tight arithmetic loop, roughly **50,000–200,000 opcodes** might execute in
that 5ms window, wildly more than 100, which illustrates how broken the old
model had become on modern hardware.

## When exactly does the GIL release?

The 5ms timer doesn't release the GIL directly. It sets the `eval_breaker` flag,
and the running thread releases the GIL the next time it checks that flag. Where
those checks happen has changed:

- **Python 3.2–3.10**: `eval_breaker` was checked at the top of every opcode
  dispatch loop iteration, so the GIL released after at most **one more
  opcode**.
- **Python 3.11+**: As part of the specializing adaptive interpreter, the check
  was moved to **backward jumps and function calls only**, a performance
  optimization that avoids the overhead of checking on every single opcode.
  A backward jump (`JUMP_BACKWARD`) is the opcode that closes a loop. It fires
  once per iteration of any `for` or `while` loop, when control returns to the
  top. Straight-line code (`if/else`, sequential statements) only jumps forward
  and never triggers a check.

The practical implication: in Python 3.11+, a straight-line sequence of
opcodes with no loop back-edge or function call will not be interrupted by the
timer. The `LOAD / BINARY_OP / STORE` sequence for `counter += 1` contains none
of those check points, which is a significant reason why naïve race-condition
demos almost never fail with the GIL active.

Note that in a tight loop with a short body, `JUMP_BACKWARD` fires on every
iteration, but the GIL only actually releases when the 5ms timer has also
elapsed. The check point and the timer work together: the check point is *where*
the GIL can release, and the timer controls *when*.

## Cooperative vs. preemptive switching

The most familiar form of context switching is **cooperative**: a lock is
acquired on entry to a critical section and released on exit. The programmer
controls exactly where switches can occur. The downside is that a thread that
never yields can starve everything else.

**Preemptive switching** (whether by instruction count or by time) hands that
decision to the scheduler. No thread can starve others, but switches can happen
*anywhere*, including places the programmer never considered. That is precisely
the source of the race in `counter += 1`: no one requested a switch between
`LOAD` and `STORE`, but the scheduler has no knowledge of that boundary.

## The GIL is a hybrid

The GIL sits between these two models:

- **Preemptive at the scheduling level**: the 5ms timer fires regardless of what
  the code is doing.
- **Cooperative at the opcode level**: the running thread only actually yields
  at the next check point (backward jump or function call in 3.11+).

What also makes the GIL unusual is that it is a *single global lock* covering
the entire interpreter, not a fine-grained lock around specific data. "Entering a
critical section" in CPython effectively means "holding the GIL," which every
thread already does whenever it runs Python code. Preemptive scheduling then
becomes: which thread next holds the single lock.

## Making the race visible: forcing a context switch

Because the 5ms timer almost never fires in the ~3 opcodes of `counter += 1`,
demos based on `counter += 1` in a tight loop rarely fail with the GIL active.
The standard fix is to split the operation manually and force a GIL release in
the middle using `time.sleep(0)`:

```python
import threading
import time

counter = 0

def increment(iterations):
    global counter
    for _ in range(iterations):
        temp = counter      # LOAD
        time.sleep(0)       # release GIL → another thread runs here
        counter = temp + 1  # STORE (may overwrite another thread's write)
```

`time.sleep()` is a blocking call, and all blocking calls release the GIL. This
guarantees a context switch occurs between every `LOAD` and `STORE`, making
lost increments a certainty rather than a rare event, even with the GIL active.

With 8 threads and 50 iterations each, the expected result is 400. A typical run
produces something in the 40–100 range.

### Why this still matters with the free-threaded build

In Python's free-threaded build (`3.14t`, no GIL), `context_switch.py` fails
without the `sleep(0)` for a more fundamental reason: there is no longer any
implicit mutual exclusion to accidentally rely on. The `sleep(0)` demo is useful
precisely because it shows the race *with the GIL active*, making the point that
the GIL does not protect you from race conditions; it only makes them unlikely
by serializing opcode execution.

## Summary

| Topic | Key point |
|---|---|
| Opcode count | ~100–130 named; ~180–220 including adaptive variants |
| Old switch interval | Every 100 opcodes (Python 1.0–3.1) |
| Current switch interval | Every 5ms via `eval_breaker` flag (Python 3.2+) |
| Check point location | Every opcode (3.2–3.10); backward jumps + calls only (3.11+) |
| GIL model | Preemptive scheduling, cooperative yield points |
| Forcing a race | `time.sleep(0)` releases the GIL between LOAD and STORE |
