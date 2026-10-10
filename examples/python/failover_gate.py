"""Educational failover decision gate, NOT a fencing service or HA controller.

Production promotion requires a separately trusted fencing authority with
durable quorum/leadership and a way to prevent the old primary from writing.
This module models decision ordering and fail-closed behavior only.
"""
from dataclasses import dataclass
from typing import Callable

@dataclass(frozen=True)
class FenceReceipt:
    target: str
    epoch: int
    evidence: str

class PromotionGate:
    def __init__(self, fence: Callable, verify: Callable, promote: Callable):
        self._fence = fence
        self._verify = verify
        self._promote = promote
        self.epoch = 0
        self.current_primary = None

    def attempt(self, old_primary: str, candidate: str, suspected_failure: bool):
        if not old_primary or not candidate or old_primary == candidate:
            raise ValueError("distinct nonempty node identifiers required")
        if not suspected_failure:
            return "no-failover"
        if self.current_primary == candidate:
            return "already-promoted"
        self.epoch += 1
        epoch = self.epoch
        receipt = self._fence(old_primary, epoch)
        if (not isinstance(receipt, FenceReceipt)
            or receipt.target != old_primary or receipt.epoch != epoch
            or not receipt.evidence or not self._verify(receipt)):
            return "blocked-unfenced"
        # Never call promote unless the trusted verifier accepted the fence.
        self._promote(candidate)
        self.current_primary = candidate
        return "promoted"
