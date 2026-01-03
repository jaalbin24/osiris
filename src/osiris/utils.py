"""Shared formatting utilities."""

from datetime import UTC, datetime


def parse_timestamp(iso_string: str) -> datetime:
    """
    Parse ISO timestamp from restic, handling Z suffix.

    Restic outputs timestamps like "2026-01-03T02:00:00.123456789Z".
    This function handles the Z suffix and returns a timezone-aware datetime.

    Usage:
        created_dt = parse_timestamp(snapshot["time"])
        age = datetime.now(timezone.utc) - created_dt
    """
    # Handle Z suffix (UTC indicator)
    if iso_string.endswith("Z"):
        iso_string = iso_string[:-1] + "+00:00"

    # Handle nanosecond precision (Python only supports microseconds)
    # Truncate to microseconds if needed
    if "." in iso_string:
        base, frac_and_tz = iso_string.split(".", 1)
        # Find where timezone starts (+ or - after the decimal)
        frac = frac_and_tz
        tz = ""
        for i, c in enumerate(frac_and_tz):
            if c in "+-":
                frac = frac_and_tz[:i]
                tz = frac_and_tz[i:]
                break

        # Truncate to 6 digits (microseconds)
        frac = frac[:6].ljust(6, "0")
        iso_string = f"{base}.{frac}{tz}"

    return datetime.fromisoformat(iso_string)


def format_age(dt: datetime) -> str:
    """
    Format a datetime as a human-readable age string.

    Examples:
        "just now", "5 minutes ago", "2 hours ago", "3 days ago"
    """
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    delta = now - dt
    seconds = delta.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


def format_size(bytes_count: int) -> str:
    """
    Format bytes as human-readable size.

    Examples:
        format_size(1024) -> "1.0 KB"
        format_size(1536000) -> "1.5 MB"
        format_size(2147483648) -> "2.0 GB"
    """
    value = float(bytes_count)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(value) < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def format_duration(seconds: float) -> str:
    """
    Format seconds as human-readable duration.

    Examples:
        format_duration(45) -> "45s"
        format_duration(125) -> "2m 5s"
        format_duration(3725) -> "1h 2m 5s"
    """
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        secs = int(seconds % 60)
        return f"{hours}h {minutes}m {secs}s"
