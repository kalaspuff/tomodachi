import pytest

from tomodachi.helpers.build_time import get_time_since_build


@pytest.mark.parametrize(
    "timestamp, build_time, expected_result",
    [
        ("2023-08-01T00:00:40.000000Z", "2023-08-01T00:00:00.000000Z", "released just now"),
        ("2023-08-01T00:01:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 1 minute ago"),
        ("2023-08-01T00:01:25.000000Z", "2023-08-01T00:00:00.000000Z", "released 1 minute ago"),
        ("2023-08-01T00:01:59.000000Z", "2023-08-01T00:00:00.000000Z", "released 1 minute ago"),
        ("2023-08-01T00:02:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 2 minutes ago"),
        ("2023-08-01T00:30:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 30 minutes ago"),
        ("2023-08-01T00:59:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 59 minutes ago"),
        ("2023-08-01T01:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 1 hour ago"),
        ("2023-08-01T01:59:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 1 hour ago"),
        ("2023-08-01T02:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 2 hours ago"),
        ("2023-08-01T12:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 12 hours ago"),
        ("2023-08-01T23:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 23 hours ago"),
        ("2023-08-02T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 1 day ago"),
        ("2023-08-02T23:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 1 day ago"),
        ("2023-08-03T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 2 days ago"),
        ("2023-09-01T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 31 days ago"),
        ("2023-09-11T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 41 days ago"),
        ("2023-10-11T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 71 days ago"),
        ("2023-11-01T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 3 months ago"),
        ("2024-11-01T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 15 months ago"),
        ("2025-07-01T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 23 months ago"),
        ("2025-07-20T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released 23 months ago"),
        ("2025-07-21T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released over 2 years ago"),
        ("2025-08-01T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released over 2 years ago"),
        ("2026-07-01T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released over 2 years ago"),
        ("2026-08-01T00:00:00.000000Z", "2023-08-01T00:00:00.000000Z", "released over 3 years ago"),
    ],
)
def test_build_time_delta_str(timestamp: str, build_time: str, expected_result: str) -> None:
    assert get_time_since_build(timestamp, build_time) == expected_result
