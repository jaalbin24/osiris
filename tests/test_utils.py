"""Tests for utility functions."""

from datetime import UTC, datetime

from osiris.utils import format_age, format_duration, format_size, parse_timestamp


class TestParseTimestamp:
    """Tests for parse_timestamp function."""

    def test_parse_with_z_suffix(self):
        """Test parsing timestamp with Z suffix."""
        result = parse_timestamp("2026-01-03T02:00:00Z")
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 3
        assert result.hour == 2
        assert result.tzinfo is not None

    def test_parse_with_nanoseconds(self):
        """Test parsing timestamp with nanosecond precision."""
        result = parse_timestamp("2026-01-03T02:00:00.123456789Z")
        assert result.microsecond == 123456
        assert result.tzinfo is not None

    def test_parse_with_timezone_offset(self):
        """Test parsing timestamp with timezone offset."""
        result = parse_timestamp("2026-01-03T02:00:00+05:00")
        assert result.hour == 2


class TestFormatAge:
    """Tests for format_age function."""

    def test_just_now(self):
        """Test 'just now' for recent timestamps."""
        now = datetime.now(UTC)
        result = format_age(now)
        assert result == "just now"

    def test_minutes_ago(self):
        """Test minutes ago formatting."""
        from datetime import timedelta

        dt = datetime.now(UTC) - timedelta(minutes=5)
        result = format_age(dt)
        assert "5 minutes ago" in result

    def test_hours_ago(self):
        """Test hours ago formatting."""
        from datetime import timedelta

        dt = datetime.now(UTC) - timedelta(hours=3)
        result = format_age(dt)
        assert "3 hours ago" in result

    def test_days_ago(self):
        """Test days ago formatting."""
        from datetime import timedelta

        dt = datetime.now(UTC) - timedelta(days=2)
        result = format_age(dt)
        assert "2 days ago" in result

    def test_singular_forms(self):
        """Test singular forms (1 minute, 1 hour, 1 day)."""
        from datetime import timedelta

        dt = datetime.now(UTC) - timedelta(minutes=1)
        assert "1 minute ago" in format_age(dt)

        dt = datetime.now(UTC) - timedelta(hours=1)
        assert "1 hour ago" in format_age(dt)

        dt = datetime.now(UTC) - timedelta(days=1)
        assert "1 day ago" in format_age(dt)


class TestFormatSize:
    """Tests for format_size function."""

    def test_bytes(self):
        """Test formatting small sizes in bytes."""
        assert format_size(512) == "512.0 B"
        assert format_size(0) == "0.0 B"

    def test_kilobytes(self):
        """Test formatting sizes in KB."""
        assert format_size(1024) == "1.0 KB"
        assert format_size(1536) == "1.5 KB"

    def test_megabytes(self):
        """Test formatting sizes in MB."""
        assert format_size(1048576) == "1.0 MB"
        assert format_size(1572864) == "1.5 MB"

    def test_gigabytes(self):
        """Test formatting sizes in GB."""
        assert format_size(1073741824) == "1.0 GB"
        assert format_size(2147483648) == "2.0 GB"

    def test_terabytes(self):
        """Test formatting sizes in TB."""
        assert format_size(1099511627776) == "1.0 TB"


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_seconds_only(self):
        """Test formatting durations under a minute."""
        assert format_duration(45) == "45s"
        assert format_duration(0) == "0s"

    def test_minutes_and_seconds(self):
        """Test formatting durations in minutes."""
        assert format_duration(125) == "2m 5s"
        assert format_duration(60) == "1m 0s"

    def test_hours_minutes_seconds(self):
        """Test formatting durations in hours."""
        assert format_duration(3725) == "1h 2m 5s"
        assert format_duration(3600) == "1h 0m 0s"
