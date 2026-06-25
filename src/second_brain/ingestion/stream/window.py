from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WindowStats:
    device_id: str
    zone_id: str
    metric: str
    count: int = 0
    mean: float = 0.0
    stdev: float = 0.0
    last_value: float = 0.0
    values: list[float] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def update(self, value: float, max_samples: int = 50) -> None:
        self.values.append(value)
        if len(self.values) > max_samples:
            self.values = self.values[-max_samples:]
        self.count = len(self.values)
        self.mean = statistics.fmean(self.values)
        self.stdev = statistics.pstdev(self.values) if self.count > 1 else 0.0
        self.last_value = value
        self.updated_at = datetime.utcnow()

    def is_anomaly(self, sigma: float = 3.0) -> bool:
        if self.count < 5:
            return False
        baseline = self.values[:-1]
        if len(baseline) < 4:
            return False
        mean = statistics.fmean(baseline)
        stdev = statistics.pstdev(baseline) if len(baseline) > 1 else 0.0
        if stdev == 0:
            return abs(self.last_value - mean) > 1e-6
        return abs(self.last_value - mean) > sigma * stdev

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "zone_id": self.zone_id,
            "metric": self.metric,
            "count": self.count,
            "mean": round(self.mean, 4),
            "stdev": round(self.stdev, 4),
            "last_value": self.last_value,
            "anomaly": self.is_anomaly(),
            "updated_at": self.updated_at.isoformat(),
        }
