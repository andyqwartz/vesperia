"""Indexation de la semaine (Europe/Paris) : wh = jour (lundi 0) * 24 + heure."""
from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")


def week_hour(ts):
    if ts.tzinfo is None:
        raise ValueError("horodatage sans fuseau")
    local = ts.astimezone(PARIS)
    return local.weekday() * 24 + local.hour


def week_hour_from_period_end(ts):
    if ts.tzinfo is None:
        raise ValueError("horodatage sans fuseau")
    return week_hour(ts.astimezone(timezone.utc) - timedelta(hours=1))