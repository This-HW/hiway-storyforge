"""Tests for storyforge.scheduler."""
import unittest
from datetime import date

from storyforge.scheduler import MIN_INTERVAL_MINUTES, generate_schedule


def make_channels():
    return {
        "animal": {
            "posting": {
                "timezone": "Asia/Seoul",
                "slots": [{"start": "18:00", "end": "21:00", "count": 1}],
            }
        },
        "property": {
            "posting": {
                "timezone": "Asia/Seoul",
                "slots": [{"start": "18:00", "end": "21:00", "count": 1}],
            }
        },
    }


class TestGenerateSchedule(unittest.TestCase):
    def test_returns_both_channels_one_time_each(self):
        sched = generate_schedule(make_channels(), date(2026, 11, 3))
        self.assertEqual(set(sched.keys()), {"animal", "property"})
        self.assertTrue(all(len(v) == 1 for v in sched.values()))

    def test_times_within_slot_and_timezone_aware(self):
        sched = generate_schedule(make_channels(), date(2026, 11, 3))
        for times in sched.values():
            for t in times:
                self.assertTrue(18 <= t.hour < 21 or (t.hour == 21 and t.minute == 0))
                self.assertIsNotNone(t.tzinfo)

    def test_min_interval_enforced(self):
        sched = generate_schedule(make_channels(), date(2026, 11, 3))
        all_times = sorted(t for v in sched.values() for t in v)
        if len(all_times) >= 2:
            gap = abs((all_times[1] - all_times[0]).total_seconds()) / 60
            self.assertGreaterEqual(gap, MIN_INTERVAL_MINUTES)

    def test_multi_slot_count(self):
        ch = {
            "multi": {
                "posting": {
                    "timezone": "Asia/Seoul",
                    "slots": [
                        {"start": "09:00", "end": "11:00", "count": 1},
                        {"start": "18:00", "end": "21:00", "count": 2},
                    ],
                }
            }
        }
        sched = generate_schedule(ch, date(2026, 11, 3))
        self.assertEqual(len(sched["multi"]), 3)

    def test_different_timezones(self):
        ch_tz = {
            "kr": {"posting": {"timezone": "Asia/Seoul",
                               "slots": [{"start": "18:00", "end": "21:00", "count": 1}]}},
            "us": {"posting": {"timezone": "America/New_York",
                               "slots": [{"start": "18:00", "end": "21:00", "count": 1}]}},
        }
        sched = generate_schedule(ch_tz, date(2026, 11, 3))
        self.assertEqual(len(sched["kr"]), 1)
        self.assertEqual(len(sched["us"]), 1)

    def test_legacy_time_window(self):
        ch_old = {
            "legacy": {
                "posting": {
                    "timezone": "Asia/Seoul",
                    "time_window": ["18:00", "21:00"],
                }
            }
        }
        sched = generate_schedule(ch_old, date(2026, 11, 3))
        self.assertEqual(len(sched["legacy"]), 1)

    def test_missing_slots_raises(self):
        with self.assertRaises(ValueError):
            generate_schedule({"bad": {"posting": {"timezone": "Asia/Seoul"}}})


if __name__ == "__main__":
    unittest.main()


def test_overlapping_slots_cannot_violate_interval():
    import pytest
    channels = make_channels()
    for cfg in channels.values():
        cfg["posting"]["slots"] = [{"start": "18:00", "end": "18:05", "count": 1}]
    with pytest.raises(ValueError):
        generate_schedule(channels)
