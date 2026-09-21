"""
Human Clicker - Generates human-like click intervals using clustered timing.

Instead of purely random intervals between min/max, this generates clusters
of similar-timed clicks that drift over time - mimicking how a real human
would click in bursts of similar rhythm before naturally shifting tempo.
"""

import random
import math


class HumanClicker:
    """
    Generates click intervals that mimic human behavior.

    The key insight: humans don't click uniformly randomly. They settle into
    a rhythm for a few clicks, then drift to a new rhythm. This creates
    "clusters" of similar intervals with natural variation within each cluster.

    Example output sequence:
        2.31, 2.45, 2.38, 2.52,   # cluster around ~2.4s
        2.41, 2.67,                 # slight drift
        3.12, 3.35, 3.21, 3.08,   # new cluster around ~3.2s
        3.45, 3.71, 3.89,         # drifting higher
        2.84, 2.61, 2.53,         # drops back down
        ...
    """

    def __init__(self, min_interval=2.0, max_interval=4.0):
        self.min_interval = min_interval
        self.max_interval = max_interval

        # Cluster state
        self._cluster_center = None    # Current cluster's center interval
        self._clicks_in_cluster = 0    # How many clicks in current cluster
        self._cluster_size = 0         # How many clicks this cluster should last
        self._drift_direction = 0      # Which way the cluster is drifting

    def _start_new_cluster(self):
        """Pick a new cluster center and size."""
        # Cluster center: weighted toward the lower end (humans tend to click
        # faster more often, with occasional slower periods)
        range_size = self.max_interval - self.min_interval

        # Use beta distribution to bias toward lower intervals
        # alpha=2, beta=3 gives a nice skew toward faster clicks
        raw = random.betavariate(2, 3)
        self._cluster_center = self.min_interval + raw * range_size

        # Cluster lasts 3-7 clicks before a new rhythm emerges
        self._cluster_size = random.randint(3, 7)
        self._clicks_in_cluster = 0

        # Drift: slight tendency to speed up or slow down within a cluster
        self._drift_direction = random.uniform(-0.04, 0.04)

    def next_interval(self):
        """
        Get the next click interval in seconds.

        Returns:
            float: seconds to wait before the next click
        """
        # Start a new cluster if needed
        if self._cluster_center is None or self._clicks_in_cluster >= self._cluster_size:
            self._start_new_cluster()

        # Base interval = cluster center + accumulated drift
        drift = self._drift_direction * self._clicks_in_cluster
        base = self._cluster_center + drift

        # Add per-click jitter (small noise around the cluster center)
        # Humans have ~50-150ms of natural timing variance
        jitter = random.gauss(0, 0.08)

        # Occasional micro-hesitation (human gets distracted briefly)
        if random.random() < 0.08:  # ~8% chance
            jitter += random.uniform(0.15, 0.4)

        interval = base + jitter

        # Clamp to bounds
        interval = max(self.min_interval, min(self.max_interval, interval))

        self._clicks_in_cluster += 1

        return round(interval, 3)

    def preview(self, count=20):
        """
        Generate a preview of intervals (for debugging/display).

        Args:
            count: Number of intervals to generate

        Returns:
            list of floats
        """
        # Save state
        old_center = self._cluster_center
        old_clicks = self._clicks_in_cluster
        old_size = self._cluster_size
        old_drift = self._drift_direction

        # Reset for clean preview
        self._cluster_center = None

        intervals = [self.next_interval() for _ in range(count)]

        # Restore state
        self._cluster_center = old_center
        self._clicks_in_cluster = old_clicks
        self._cluster_size = old_size
        self._drift_direction = old_drift

        return intervals
