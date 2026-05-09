# async_fetch.py
"""
Cooperative I/O concurrency. A coroutine pauses at `await`, the event
loop runs other coroutines, then resumes the original when its awaited
task is ready. asyncio.sleep simulates an I/O wait without an external
network dependency.
"""

import asyncio


async def fetch(name: str, delay: float) -> str:
    print(f"  start {name}")
    await asyncio.sleep(delay)  # simulates I/O latency
    print(f"  done  {name}")
    return f"result for {name}"


async def main() -> None:
    results = await asyncio.gather(
        fetch("a", 0.3),
        fetch("b", 0.1),
        fetch("c", 0.2),
    )
    print(results)


if __name__ == "__main__":
    asyncio.run(main())
