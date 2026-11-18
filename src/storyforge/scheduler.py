"""Draw posting times in channel-local slots with an account-wide interval."""
from datetime import date, datetime, time
import random
from functools import lru_cache
from zoneinfo import ZoneInfo

MIN_INTERVAL_MINUTES = 10


def generate_schedule(channels: dict, on_date: date | None = None) -> dict:
    result = {name: [] for name in channels}
    requests = []
    for name, cfg in channels.items():
        posting = cfg.get("posting", {})
        zone = ZoneInfo(posting.get("timezone", "Asia/Seoul"))
        day = on_date or datetime.now(zone).date()
        slots = posting.get("slots")
        if slots is None and "time_window" in posting:
            start, end = posting["time_window"]
            slots = [{"start": start, "end": end}]
        if not slots:
            raise ValueError(f"{name}: 게시 시간 구간이 필요합니다")
        for slot in slots:
            start, end = (datetime.combine(day, time.fromisoformat(slot[k]), zone)
                          for k in ("start", "end"))
            count = slot.get("count", 1)
            if type(count) is not int or count < 1 or end < start:
                raise ValueError(f"{name}: 게시 시간 또는 건수가 올바르지 않습니다")
            first, last = int(start.timestamp() // 60), int(end.timestamp() // 60)
            if (count - 1) * MIN_INTERVAL_MINUTES > last - first:
                raise ValueError(f"{name}: 게시 간격을 확보할 수 없습니다")
            requests.extend([(name, zone, first, last)] * count)

    # For a fixed chronological order, the earliest placement leaves maximum
    # room for later jobs. Search orders only, then randomize their slack.
    random.shuffle(requests)
    requests.sort(key=lambda r: r[3])

    @lru_cache(maxsize=None)
    def order(remaining, earliest):
        if not remaining:
            return ()
        if any(requests[i][3] < earliest for i in remaining):
            return None
        tried = set()
        for i in remaining:
            _, _, first, last = requests[i]
            if (first, last) in tried:
                continue
            tried.add((first, last))
            following = tuple(j for j in remaining if j != i)
            tail = order(following, max(first, earliest) + MIN_INTERVAL_MINUTES)
            if tail is not None:
                return (i,) + tail
        return None

    if not requests:
        return result
    first_minute = min(r[2] for r in requests)
    sequence = order(tuple(range(len(requests))), first_minute)
    if sequence is None:
        raise ValueError("채널 간 게시 간격을 확보할 수 없습니다")
    latest = {}
    limit = max(r[3] for r in requests)
    for i in reversed(sequence):
        latest[i] = min(requests[i][3], limit)
        limit = latest[i] - MIN_INTERVAL_MINUTES
    earliest = first_minute
    for i in sequence:
        name, zone, first, _ = requests[i]
        minute = random.randint(max(first, earliest), latest[i])
        result[name].append(datetime.fromtimestamp(minute * 60, zone))
        earliest = minute + MIN_INTERVAL_MINUTES
    return result
