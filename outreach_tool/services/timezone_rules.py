from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from config import COUNTRY_TIMEZONE_MAP


@dataclass
class BusinessHoursCheck:
    valid_country: bool
    within_business_hours: bool
    timezone_name: str | None
    local_time: datetime | None
    reason: str | None = None


def resolve_timezone(country: str) -> str | None:
    if not country:
        return None
    return COUNTRY_TIMEZONE_MAP.get(country.strip().lower())


def check_business_hours(country: str, now_utc: datetime | None = None) -> BusinessHoursCheck:
    timezone_name = resolve_timezone(country)
    if not timezone_name:
        return BusinessHoursCheck(
            valid_country=False,
            within_business_hours=False,
            timezone_name=None,
            local_time=None,
            reason="Invalid_Country",
        )

    utc_now = now_utc or datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
    local_time = utc_now.astimezone(ZoneInfo(timezone_name))
    weekday_ok = local_time.weekday() < 5
    in_hours = (local_time.hour > 9 or (local_time.hour == 9 and local_time.minute >= 0)) and (
        local_time.hour < 18
    )

    if weekday_ok and in_hours:
        return BusinessHoursCheck(True, True, timezone_name, local_time)

    return BusinessHoursCheck(
        valid_country=True,
        within_business_hours=False,
        timezone_name=timezone_name,
        local_time=local_time,
        reason="Deferred_Outside_Business_Hours",
    )
