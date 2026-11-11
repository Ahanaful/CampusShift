"""UTC storage and explicit department-local/DST conversion policies."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

UTC = timezone.utc


def now_utc():
    return datetime.now(UTC)


class UTCTimestamp(TypeDecorator):
    """SQLite stores canonical, sortable ISO timestamps including the UTC Z."""
    impl = String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Attendance timestamps must be timezone-aware")
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    def process_result_value(self, value, dialect):
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def zone(name):
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        raise ValueError("Department timezone is unavailable; install tzdata and check configuration") from None


def local_to_utc(value, timezone_name, fold=0):
    if value.tzinfo is not None:
        return value.astimezone(UTC)
    tz = zone(timezone_name)
    local = value.replace(tzinfo=tz, fold=fold)
    result = local.astimezone(UTC)
    if result.astimezone(tz).replace(tzinfo=None) != value:
        raise ValueError("This local time does not exist during the daylight-saving transition. Choose a valid time.")
    return result


def shift_instants(shift, timezone_name):
    # Existing schedules have no fold field: repeated times use first occurrence.
    start = local_to_utc(datetime.combine(shift.shift_date, shift.start_time), timezone_name)
    end = local_to_utc(datetime.combine(shift.shift_date, shift.end_time), timezone_name)
    if end <= start:
        raise ValueError("Scheduled interval does not produce a positive elapsed duration")
    return start, end
