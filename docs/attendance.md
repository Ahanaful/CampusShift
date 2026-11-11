# Attendance design and local operation

## Persistence and audit

Alembic revision `9e57ab896061` adds `AttendanceRecord`, `AttendanceCorrection`, and `AttendanceEvent` without modifying existing schedules. Records retain their original student, department and assigned-shift FK; that FK restricts deletion of historical shifts. A unique shift FK prevents duplicate attendance. A partial unique index permits at most one active record per student globally, including if a department changes later. Another partial unique index permits one pending correction per record. Database checks enforce timestamp/status consistency and positive completed/proposed intervals.

Record statuses are active, completed, corrected, and missing. Missing is a null-timestamp placeholder created only when a student requests a missed-clock-in correction; it contributes zero actual hours. Correction statuses are pending, approved and rejected. Each decision records reviewer, UTC time, note and the original proposal. Attendance events retain original/before/after timestamps and versions; students cannot directly edit completed attendance or audit history. No API deletes attendance records or events.

Services reserve SQLite's write lock before reads/validation/writes, making duplicate clock attempts and overlapping approvals serial. Concurrent clock-in tests use file-backed SQLite and confirm one success and one 409. Record versions protect pending corrections against later clock-out or other approved changes. A stale proposal cannot be approved; the supervisor can reject it and request resubmission. Record changes, correction decisions and audit events commit atomically. Failed audit writes roll back the attendance mutation.

## Server clock and eligibility

Clock-in accepts only an assigned-shift ID. The authenticated student and department are authoritative. The referenced run must currently be published and belong to that student; drafts and archived versions cannot start new attendance. A previously active record may always be clocked out by its owner even if its original publication is now archived. Inactive students cannot start work. API inputs forbid extra timestamp/student/status fields.

Server UTC now must be at least `scheduled_start - CLOCK_IN_EARLY_MINUTES`, at most `scheduled_start + CLOCK_IN_LATE_MINUTES`, and strictly before scheduled end. Defaults are 15 minutes early and 30 minutes late. Repeats return 409; ownership failures 404, role failures 403, unauthenticated requests 401 and invalid timing 422. Clock-out requires a positive interval and an active owned record. No automatic clock-out or truncation of long-running attendance occurs; supervisors review discrepancies.

Late means recorded clock-in is more than `ATTENDANCE_LATE_GRACE_MINUTES` after planned start (default five). Missed means a current published shift ended without recorded clock-in, including missing placeholders. Superseded unrecorded shifts are excluded from supervisor missed counts so publication replacement does not manufacture absences. Recorded historical shifts remain visible and keep their planned duration for comparison.

## Corrections

Students propose both clock timestamps and a reason, including when correcting an active record after forgetting clock-out. A proposal must end no later than server now, start before end, last no more than 24 actual hours, and start on the original shift's department-local date or the preceding night if the interval continues past scheduled start. End may be after midnight. For a missing record or active forgotten-clock-out, wait until scheduled end; active students should otherwise use clock-out. Existing recorded attendance may be corrected after completion. Current or archived published shifts may be selected for historical correction.

Proposals are checked for overlaps at submission and again at approval, excluding the record being corrected. Active records are open-ended intervals; approved corrections cannot overlap them. Half-open boundaries permit adjacent attendance. Pending proposals do not alter actual values or totals. Rejection preserves the original working attendance values. Approval applies both proposed times as one corrected interval and closes a forgotten active record. All original values remain in events and the correction proposal is retained.

## UTC, local dates, midnight and DST

`core/attendance_time.py` provides a SQLAlchemy `UTCTimestamp` type that stores fixed-microsecond ISO strings ending in Z. They sort chronologically and deserialize to timezone-aware UTC values. It rejects naive values at persistence. SQLite does not preserve timezone metadata on ordinary DATETIME columns, so attendance uses explicit UTC text rather than silently dropping offsets. New audit, record and proposal fields all use this representation; older phase timestamps are unchanged.

Published shifts remain local calendar dates and wall-clock times. ZoneInfo with the pinned `tzdata` dependency converts them using the configured department IANA zone. Ambiguous scheduled times use the first occurrence (fold 0). A nonexistent spring-forward time is rejected with an actionable error instead of guessed. Corrections accept aware ISO timestamps, or naive local timestamps interpreted in the department timezone with optional fold 0/1 selectors. The UI sends local inputs with explicit fold choices. It displays timestamps with department timezone abbreviations so repeated hours can be distinguished.

Actual hours are elapsed UTC seconds, not scheduler wall-clock minutes. For example, America/Chicago 00:30–02:30 across fall-back is three actual hours versus two planned hours; 01:30–03:30 across spring-forward is one actual hour versus two planned. Clock-out can cross midnight. Weekly actual hours intersect attendance intervals with UTC instants representing local Monday 00:00 through next Monday 00:00; DST weeks can therefore contain 167/169 elapsed hours. Running attendance uses a server-observed snapshot; there is no payroll rounding or wage calculation.

## Reporting and interface

Student **My attendance** shows next/today published shifts, eligible clock actions, current active state, actual local-week hours, history and correction requests. Supervisors see a department-only active list, planned/actual comparison, recorded late clock-ins, ended missed shifts, correction decisions and CSV export. Screens poll attendance every 30 seconds and offer manual refresh; there is no push delivery.

History date filters use the original scheduled department-local shift date. Status filters apply to attendance rows, not planned shift totals or active lists. Active lists ignore date/status filters but honor a supervisor's employee filter. Weekly actual hours ignore date/status filters and honor the employee filter. Planned summary hours count current publications in the selected date/student range; actual history retains attendance on archived original shifts. CSV exports the filtered record rows, not unrecorded planned-shift indicators. CSV timestamps are UTC; spreadsheet-formula prefixes in student/location text are escaped.

All report and correction queries scope by authenticated department. Students cannot select another identity through query/body fields. Export is supervisor-only and downloaded through the centralized bearer-authenticated client; tokens never enter URLs. Application logs contain action/actor/record IDs and denied shift attempts. No device, GPS or biometric fields are collected.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/students/me/attendance` | Own active state, shifts, history and actual-hour summaries |
| POST | `/api/students/me/attendance/clock-in` | `{assigned_shift_id}`; server timestamp only |
| POST | `/api/students/me/attendance/{id}/clock-out` | Empty JSON `{}`; server timestamp only |
| GET, POST | `/api/students/me/attendance/corrections` | Own requests / `{assigned_shift_id,proposed_clock_in,proposed_clock_out,reason,clock_in_fold?,clock_out_fold?}` |
| GET | `/api/students/me/attendance/{id}/audit` | Own record's original values and changes |
| GET | `/api/supervisor/attendance` | Department report; optional `student_id,start_date,end_date,status` |
| GET | `/api/supervisor/attendance/export.csv` | Same record filters; authenticated CSV |
| GET | `/api/supervisor/attendance/corrections` | Department correction queue/history; optional `status` |
| POST | `/api/supervisor/attendance/corrections/{id}/decision` | `{status:approved|rejected,reviewer_note?}` |
| GET | `/api/supervisor/attendance/{id}/audit` | Department record audit |

## Local checks and demonstration

Use the README's virtual-environment setup, install backend requirements and the root scheduler package, run `alembic upgrade head`, then start Uvicorn and Vite. Preserve an existing `.env`; add optional clock policy variables as needed. No credentials or cloud services are required.

Generate and publish a shift whose start is within the configured clock-in window, using a location-eligible student with availability. Clock in/out as that student; monitor live state as supervisor. Submit a past correction and approve/reject it; inspect original values through Audit. Publish a replacement week and confirm original attendance still references the archived shift. Export as supervisor and confirm student export returns 403. Deterministic tests patch the server clock internally; the deployed API has no test-time override or user-supplied clock timestamps.

Run `python -m unittest discover -s tests -v` from backend and the independent scheduler tests from the root, then frontend lint/build. Tests include clock windows, duplicates, real concurrency, ownership/department isolation, UTC storage, midnight/local-week clipping, DST folds/gaps, actual-versus-scheduled DST duration, corrections, overlapping approvals, retained historical associations, atomic failures and CSV authorization/formula escaping.

Remaining limits: report queries are unpaginated, UI polling is not push, DST-gap schedule times need supervisor resolution, and the 24-hour correction limit is a local policy rather than a configurable contract. Browser interaction requires manual verification in this environment. AWS, DynamoDB migration, GPS, biometrics, payroll, wage calculations and email/SMS remain outside Phase 5.
