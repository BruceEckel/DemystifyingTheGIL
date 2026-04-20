# Introduction: Why are we doing this?

Speed. Only start messing with this if things aren't running fast enough.

The complexity jump is big: all of a sudden you must think about things that you've previously been able to ignore.
If your system is already fast enough, don't wade into this.

If it's not fast enough, first consider simpler alternatives (use Occam's razor):

- Profile your system and identify bottleneck functions. Convert these into Rust modules via PyO3; using AI this is now surprisingly straightforward and reliable. It sidesteps the whole question rather than working around it.

- NumPy / SciPy / array-oriented libraries.
  If your CPU bottleneck is numeric work, the answer is often "stop looping in Python." NumPy operations drop into
  C/Fortran, release the GIL, and are already parallelized internally (via BLAS, LAPACK, etc.). No threading required.

- Dask / Ray / joblib.
  Distributed task schedulers handle parallelism above the process level. Dask in particular integrates with
  NumPy/Pandas idioms. Good when the dataset or compute exceeds a single machine.

- GPU compute (CuPy, PyTorch, JAX).
  For the right workloads (dense numeric, ML), the GPU has thousands of cores and bypasses the GIL entirely. Not
  universally applicable, but when it fits, nothing else competes.

- mmap + worker processes reading shared data.
  For the large-dataset-in-memory problem: memory-map a file and let multiple processes read it without copying. The OS
  handles sharing at the page level.
