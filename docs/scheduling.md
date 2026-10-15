# Scheduling design

## Separation and transactions

`scheduler/engine.py` is a dependency-free pure Python function over immutable typed inputs. It knows no SQLAlchemy, FastAPI, React, or AWS. The repository's `pyproject.toml` installs this package into the backend environment with `pip install -e .` from the root (`pip install -e ..` from backend). Its own tests need only Python.

`backend/app/services/scheduling.py` loads a department-scoped snapshot, adapts recurring windows, calls the engine, and saves a new `ScheduleRun`, `AssignedShift` rows, and `UnfilledRequirement` rows in one transaction. SQLite acquires a write reservation before loading the snapshot. Any persistence failure rolls back the run. New runs always get new IDs: no endpoint overwrites a saved schedule. Configuration edits affect only future generations. Names, timezone, constraints, demand, and fairness history are snapshotted for audit and historical display.

The additive Alembic revision preserves Phase 2 users, departments, classes and availability. It adds an active scheduling flag to users, a department timezone, locations/eligibility, staffing demand, and draft tables. Referenced locations and requirements are retained for history. The initial migration is unchanged. Downgrading Phase 3 removes its new data; it is not a production rollback policy.

## Hard constraints

The API loads only the supervisor's department; the engine independently excludes students/requirements outside that department. Only active students with explicit location eligibility, a positive hour limit, and full-slot availability can be assigned. Classes and already assigned shifts exclude overlapping slots. All intervals use `[start,end)`: a class ending when a shift begins is allowed. Integer minutes enforce weekly caps without rounding errors. A student is selected once per slot and headcount is capped at demand. Inactive requirements and locations do not generate demand. Missing availability means unavailable. Invalid windows, overlapping active requirements at the same location, duplicate input IDs, invalid headcounts, and non-Monday starts are rejected.

Requirements use 30-minute boundaries and same-day times. Classes/availability use arbitrary minute boundaries; partial 30-minute slots are conservatively left uncovered. Assignments with adjacent times, identical student, date, location and requirement merge; no zero-length assignments are created. Windows cannot cross midnight. End-of-day staffing must end on a representable same-day half-hour boundary (at latest 23:30); 24:00 is not supported in this phase.

## Ranking and fairness

For each chronological day/time slot, choose the remaining location requirement with smallest `(currently eligible student count - requested count, requirement ID)`. Recompute eligibility after every location allocation. Students are ordered by:

1. Current assigned weekly minutes divided into integer one-hour bands (`minutes // 60`).
2. Minutes assigned in the newest draft of the latest earlier scheduled week (zero if none).
3. Prefer extending a contiguous assignment for that requirement.
4. Exact current assigned minutes.
5. Stable cyclic student-ID ordering rotated by the week ordinal, then the student ID.

One-hour bands avoid splitting an otherwise continuous shift merely to equalize each half hour. Fairness remains a preference: availability, specialization, and hard limits can produce uneven hours. Historical data comes from drafts rather than actual time worked. The chosen history run ID/minutes are saved; rerunning the same week does not accumulate hours across draft versions. Permuting identical input rows does not change results.

This is a heuristic with no backtracking or optimization solver. It does not guarantee maximum coverage, perfectly equal hours, minimal fragmentation, breaks, travel time between locations, or contractual minimum shift lengths. It may miss a feasible assignment because of an earlier greedy choice. Longer-term fairness and minimum shift-length policies should be evaluated before publication is implemented.

## Metrics and gaps

Coverage is weighted by employee-minutes, not number of requirement rows. `required_staff_minutes = assigned_staff_minutes + unfilled_staff_minutes`. Required/unfilled slot positions divide their corresponding minutes by 30. Employee assigned-hour totals sum actual saved duration minutes divided by 60. Zero demand yields 100% by convention and no assignments; the frontend explicitly explains this state.

Gaps store their requirement ID, date, exact interval, missing count and an explanation. Reasons describe local exclusions at the time the greedy decision was made (eligibility, availability, classes, existing allocations, hour caps), not a proof that a different global assignment could not fill the slot. Adjacent gaps merge only when their location, requirement, date, missing count, and reason match.

## Local time and previews

Each department defaults to the IANA timezone name `America/Chicago`. Scheduling inputs/outputs are recurring local wall-clock minutes and date-only calendar arithmetic, without naive UTC conversions. Local durations are wall-clock duration even on DST-transition Sundays. `created_at` is UTC metadata and is normalized after SQLite round trips. The frontend defaults the supervisor's week picker using the department timezone and renders dates without turning them into UTC instants.

Supervisor endpoints require supervisor role and scope every ID lookup by department. Students can view only their eligible locations and own assigned shifts. Without a week filter, previews choose the most recently generated department draft (even if it is for a past or future week); a Monday filter chooses that week's newest version. Drafts are always labeled unpublished. No shift edits, publishing, approval, notifications, time-off, swaps or AWS integration are implemented. After input changes, regenerate and review a new draft; saved drafts do not automatically update or certify current constraints.
