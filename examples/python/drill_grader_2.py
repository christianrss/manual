"""Public examples for independent coding assessment II (not reference solutions).
Run after implementing unsolved_drills_2.py.
"""
from unsolved_drills_2 import minimum_batch_capacity,islands_after_activation

BATCH_CASES=[
    ([7,2,5,10,8],2,18),
    ([1,4,4],3,4),
    ([],1,0),
    ([0,0,0],2,0),
    ([5,1,2],1,8),
    ([1,2,3],5,3),
    ([9,1,3],2,9),
    ([10],10,10),
    ([2,2,2,2,2],2,6),
]
ISLAND_CASES=[
    (3,3,[(0,0),(0,1),(1,2),(1,1),(0,0)],[1,1,2,1,1]),
    (2,2,[(0,0),(1,1)],[1,2]),
    (1,5,[(0,0),(0,4),(0,2),(0,1),(0,3)],[1,2,3,2,1]),
    (1,1,[(0,0),(0,0)],[1,1]),
    (2,2,[],[]),
    (0,3,[],[]),
    (3,0,[],[]),
    (3,3,[(0,0),(0,2),(2,0),(2,2),(1,1)],[1,2,3,4,5]),
    (3,3,[(1,0),(1,2),(0,1),(2,1),(1,1)],[1,2,3,4,1]),
]
def evaluate(batcher=minimum_batch_capacity,islands=islands_after_activation):
    checked=[]
    for loads,batches,expected in BATCH_CASES:
        actual=batcher(list(loads),batches)
        if actual!=expected:
            raise AssertionError(f"batches({loads},{batches}) expected {expected}, got {actual}")
        checked.append(("capacity",len(loads)))
    for rows,columns,actions,expected in ISLAND_CASES:
        actual=islands(rows,columns,list(actions))
        if actual!=expected:
            raise AssertionError(f"islands({rows},{columns},{actions}) expected {expected}, got {actual}")
        checked.append(("islands",len(actions)))
    return checked

if __name__=="__main__":
    print(f"Passed {len(evaluate())} public cases. Add your own tests.")
