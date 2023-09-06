import datetime
from typing import Optional

from tomodachi.__version__ import __build_time__ as tomodachi_build_time


def get_time_since_build(timestamp: Optional[str] = None, build_time: Optional[str] = None) -> str:
    time_since_tomodachi_build = ""

    if not build_time:
        build_time = tomodachi_build_time

    if not timestamp:
        timestamp = (
            datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        )

    if build_time:
        try:
            tomodachi_build_datetime = datetime.datetime.strptime(build_time, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(
                datetime.timezone.utc
            )
            current_datetime = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(
                datetime.timezone.utc
            )
            timedelta_since_tomodachi_build = current_datetime - tomodachi_build_datetime
            if timedelta_since_tomodachi_build.days == 0:
                seconds = timedelta_since_tomodachi_build.seconds
                if seconds >= 3600:
                    hours = seconds // 3600
                    time_since_tomodachi_build = f"released {hours} hour{'s' if hours > 1 else ''} ago"
                elif seconds >= 60:
                    minutes = seconds // 60
                    time_since_tomodachi_build = f"released {minutes} minute{'s' if minutes > 1 else ''} ago"
                else:
                    time_since_tomodachi_build = "released just now"
            else:
                days = timedelta_since_tomodachi_build.days
                if days >= 720:
                    years = days // 365
                    if years < 2:
                        years = 2
                    time_since_tomodachi_build = f"released over {years} year{'s' if years > 1 else ''} ago"
                elif days >= 90:
                    months = days // 30
                    time_since_tomodachi_build = f"released {months} month{'s' if months > 1 else ''} ago"
                else:
                    time_since_tomodachi_build = f"released {days} day{'s' if days > 1 else ''} ago"
        except Exception:
            pass

    return time_since_tomodachi_build
