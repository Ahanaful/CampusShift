# Scheduler

Dependency-free, deterministic Phase 3 scheduling engine. `engine.generate` takes a department ID, a Monday date, immutable student inputs (including location eligibility, availability, classes, hour limits and history), and staffing requirements. It returns assignments, unfilled periods, and coverage metrics without side effects.

Install into the API environment with `backend/.venv/Scripts/python.exe -m pip install -e .` from the repository root. Run independent tests with `python -m unittest discover -s scheduler/tests -v`. See `docs/scheduling.md` for the 30-minute granularity, constraints, ranking, timezone policy, and limitations.
