# Open Questions

## Technical Gaps

**What operations ARE thread-safe, even without the GIL?**
The talk shows what breaks, but doesn't tell the audience what they can still rely on. `list.append`, `dict.__setitem__`, and a handful of other operations are atomic in CPython due to the object model, not the GIL. A one-slide summary of "safe vs. not safe" would give the audience something actionable to take home.

**When does free-threading actually make code faster?**
`no_surprise.py` shows free-threading being *slower* due to lock contention. The talk currently has no example of free-threading being *faster*. Without one, the audience may leave wondering why the GIL removal matters at all. A simple CPU-bound embarrassingly-parallel workload (e.g., hashing or compressing independent chunks) would demonstrate the upside.

**Which popular libraries are free-threading compatible today?**
The outline says "check your dependencies" but gives no specifics. The audience will immediately wonder about numpy, pandas, requests, SQLAlchemy, etc. Even a rough status ("numpy has experimental support as of 2.1; most pure-Python libraries work but haven't been tested") would make the advice concrete.

**What tools can find these bugs beyond running under 3.14t?**
The outline recommends running the test suite under 3.14t, which is good advice. Are there other tools? Thread sanitizer (`-fsanitize=thread` for C extensions), `threading.settrace` tricks, or stress-test harnesses? Even a brief mention signals to the audience that the ecosystem is developing.

## Narrative

**Is there a clear problem and resolution?**
The current arc is: GIL hides races → no-GIL exposes them → add locks. That is correct, but a sharper framing might be: the problem is *invisible assumptions*: code that works not because it is correct but because the interpreter happened to serialize things. The resolution is *making your assumptions explicit*. This reframe also applies beyond the GIL.

**Does the audience leave with one sentence?**
