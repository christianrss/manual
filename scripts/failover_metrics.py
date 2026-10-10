"""Measure controlled PostgreSQL switchover phases; not a production RTO/SLO.

Timestamps use time.monotonic(), are local to one CI runner and are never
compared against wall-clock timestamps from another machine.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class FailoverTiming:
    start: float
    old_primary_stopped: float
    standby_promoted: float
    write_committed: float

    def phases(self):
        t=(self.start,self.old_primary_stopped,self.standby_promoted,
           self.write_committed)
        if any(b<a for a,b in zip(t,t[1:])):
            raise ValueError("non-monotonic failover observations")
        return {
            "stop_s":round(t[1]-t[0],3),
            "promotion_s":round(t[2]-t[1],3),
            "new_write_s":round(t[3]-t[2],3),
            "observed_recovery_s":round(t[3]-t[0],3),
        }
