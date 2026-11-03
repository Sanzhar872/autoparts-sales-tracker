from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

TZ_NAME = "Asia/Almaty"
TZ = ZoneInfo(TZ_NAME)


def today() -> date:
    return datetime.now(TZ).date()


def at_noon(d: date) -> datetime:
    """Время операции не важно: храним полдень по Алматы, чтобы дата не сдвигалась."""
    return datetime.combine(d, time(12), TZ)


def day_start(d: date) -> datetime:
    return datetime.combine(d, time(0), TZ)


def day_end_exclusive(d: date) -> datetime:
    return day_start(d + timedelta(days=1))


def local_date(dt: datetime) -> date:
    return dt.astimezone(TZ).date()
