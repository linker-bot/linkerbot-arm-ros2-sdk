"""Conservative mapping from host reception time to the node's ROS clock."""

from collections import deque


class FeedbackClock:
    """Bracket receptions by observed ROS clock ticks, without mixing epochs.

    Use the last clock observation *before* the oldest included reception.
    This gives a conservative timestamp, rounded back by at most the interval
    between publication callbacks during normal operation. Re-reading a sample
    cannot move its stamp forward. It also works with paused/scaled ROS time;
    subtracting a wall-time age from simulated time would not.
    """

    def __init__(self, max_age_s):
        self._max_age_s = max_age_s
        self._ticks = deque()
        self._simulated = None

    def observe(self, monotonic_now, ros_ns, simulated):
        if self._ticks:
            host_prev, ros_prev = self._ticks[-1]
            host_delta = monotonic_now - host_prev
            ros_delta = (ros_ns - ros_prev) / 1e9
            if (
                simulated != self._simulated
                or host_delta < 0
                or ros_delta < 0
                # System clock adjustments over 100 ms start a new epoch.
                or (not simulated and abs(ros_delta - host_delta) > 0.1)
            ):
                self._ticks.clear()
        # Forward simulated-time steps need no reset: predecessor mapping
        # keeps pre-step samples at their old ROS stamp. Treating any large
        # step as an epoch change would starve slow/scaled /clock publishers.
        self._simulated = simulated
        if ros_ns <= 0:
            self._ticks.clear()
            return
        self._ticks.append((monotonic_now, ros_ns))
        # Retain a predecessor for every reception still within the age budget.
        cutoff = monotonic_now - self._max_age_s
        while len(self._ticks) > 1 and self._ticks[1][0] <= cutoff:
            self._ticks.popleft()

    def stamp_ns(self, received_at):
        for host_time, ros_ns in reversed(self._ticks):
            if host_time <= received_at:
                return ros_ns
        # Startup / a clock epoch change: wait for all fields to update.
        return None
