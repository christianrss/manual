"""Independent fail-closed unit tests. No claim of production fencing."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples" / "python"))
from failover_gate import FenceReceipt, PromotionGate

class PromotionSafety(unittest.TestCase):
    def test_suspicion_is_not_a_fence(self):
        actions=[]
        gate=PromotionGate(lambda old,epoch: None,lambda r: True,actions.append)
        self.assertEqual(gate.attempt("primary","standby",False),"no-failover")
        self.assertEqual(gate.attempt("primary","standby",True),"blocked-unfenced")
        self.assertEqual(actions,[])

    def test_stale_receipt_cannot_promote(self):
        actions=[]
        gate=PromotionGate(
            lambda old,epoch: FenceReceipt(old,epoch-1,"old-stale-receipt"),
            lambda receipt: True, actions.append)
        self.assertEqual(gate.attempt("a","b",True),"blocked-unfenced")
        self.assertFalse(actions)

    def test_wrong_target_and_failed_verification_are_rejected(self):
        actions=[]
        wrong=PromotionGate(lambda old,e: FenceReceipt("other",e,"test"),
                            lambda r: True,actions.append)
        self.assertEqual(wrong.attempt("a","b",True),"blocked-unfenced")
        no_verification=PromotionGate(
            lambda old,e: FenceReceipt(old,e,"test"),
            lambda r: False,actions.append)
        self.assertEqual(no_verification.attempt("a","b",True),"blocked-unfenced")
        self.assertEqual(actions,[])

    def test_valid_receipt_promotes_once_with_current_epoch(self):
        actions=[]
        receipts=[]
        def issue(old,epoch):
            proof=FenceReceipt(old,epoch,"test-fencer-confirmed-old-stopped")
            receipts.append(proof)
            return proof
        gate=PromotionGate(issue,lambda p:p in receipts,actions.append)
        self.assertEqual(gate.attempt("a","b",True),"promoted")
        self.assertEqual(gate.attempt("a","b",True),"already-promoted")
        self.assertEqual(actions,["b"])
        self.assertEqual(gate.epoch,1)

if __name__=="__main__":
    unittest.main()
