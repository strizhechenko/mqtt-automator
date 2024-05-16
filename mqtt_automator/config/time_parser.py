from datetime import time


def parse_time(time_s: str) -> time:
    return time(*map(int, time_s.split(':')))


def parse_time_range(time_range: str) -> list[time, time]:
    """
    >>> parse_time_range('19:00-23:25')
    [datetime.time(19, 0), datetime.time(23, 25)]
    """
    return [parse_time(t) for t in time_range.split('-', 1)]


def match_range(range_: str, value: int) -> bool:
    """
    No overflow required, so naive realisation is enough for both hours and minutes
    >>> match_range('3-10', 5)
    True
    >>> match_range('3-10', 2)
    False
    """
    return value in range(*map(int, range_.split('-')))


def match_time_range(time_range: str, current_time: time) -> bool:
    """
    >>> match_time_range('09:00-23:00', time(15, 0))
    True
    >>> match_time_range('09:00-23:00', time(8, 0))
    False
    >>> match_time_range('23:00-09:00', time(8, 0))
    True
    >>> match_time_range('23:00-09:00', time(15, 0))
    False
    """
    from_t, to_t = parse_time_range(time_range)
    if from_t < to_t:
        return from_t <= current_time <= to_t
    return time(0, 0) <= current_time <= to_t or from_t <= current_time <= time(23, 59)
