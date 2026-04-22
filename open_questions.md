# Open Questions for the Presentation

## Technical Gaps

**What operations ARE thread-safe, even without the GIL?**
The talk shows what breaks, but doesn't tell the audience what they can still rely on. `list.append`, `dict.__setitem__`, and a handful of other operations are atomic in CPython due to the object model, not the GIL. A one-slide summary of "safe vs. not safe" would give the audience something actionable to take home.

**When does free-threading actually make code faster?**
`no_surprise.py` shows free-threading being *slower* due to lock contention. The talk currently has no example of free-threading being *faster*. Without one, the audience may leave wondering why the GIL removal matters at all. A simple CPU-bound embarrassingly-parallel workload (e.g., hashing or compressing independent chunks) would demonstrate the upside.

**How does asyncio relate?**
Many Python developers use `asyncio` for concurrency and may conflate it with threading. The talk does not address the relationship: asyncio is cooperative, single-threaded, and unaffected by the GIL. One sentence of positioning would prevent confusion.

**Which popular libraries are free-threading compatible today?**
The outline says "check your dependencies" but gives no specifics. The audience will immediately wonder about numpy, pandas, requests, SQLAlchemy, etc. Even a rough status ("numpy has experimental support as of 2.1; most pure-Python libraries work but haven't been tested") would make the advice concrete.

**What tools can find these bugs beyond running under 3.14t?**
The outline recommends running the test suite under 3.14t, which is good advice. Are there other tools? Thread sanitizer (`-fsanitize=thread` for C extensions), `threading.settrace` tricks, or stress-test harnesses? Even a brief mention signals to the audience that the ecosystem is developing.

## Narrative

**Is there a clear villain and resolution?**
The current arc is: GIL hides races → no-GIL exposes them → add locks. That is correct, but the villain is abstract ("the GIL was lying to you"). A sharper framing might be: the villain is *invisible assumptions*: code that works not because it is correct but because the interpreter happened to serialize things. The resolution is *making your assumptions explicit*. This reframe also applies beyond the GIL.

**Does the audience leave with one sentence?**
A strong talk can be summarized in one sentence by the audience on the way out. The current closest candidate is the slide: "If two threads touch the same data and at least one writes, you need a lock (GIL or not)." Is that the sentence? Knowing it explicitly helps decide which examples to keep and which to cut.

## Housekeeping

**`opmap_contents.py` is still in the examples directory.**
It is not in the Makefile or CLAUDE.md but will appear if someone lists the directory.
