"""Exhaustively enumerate small undirected network partitions and majority eligibility.

This model proves a graph/quorum invariant under symmetric, static connectivity.
It does NOT simulate Raft elections, RabbitMQ or packet loss.
"""
from itertools import combinations

def components(nodes, links):
    if nodes < 1:
        raise ValueError("positive member count")
    adjacency=[set() for _ in range(nodes)]
    for a,b in links:
        if not (0<=a<nodes and 0<=b<nodes and a!=b):
            raise ValueError("invalid endpoint")
        adjacency[a].add(b)
        adjacency[b].add(a)
    seen=set()
    result=[]
    for start in range(nodes):
        if start in seen:
            continue
        pending=[start]
        seen.add(start)
        group=[]
        while pending:
            u=pending.pop()
            group.append(u)
            for v in adjacency[u]:
                if v not in seen:
                    seen.add(v)
                    pending.append(v)
        result.append(frozenset(group))
    return result

def eligible_majority_components(nodes, links):
    threshold=nodes//2+1
    return [group for group in components(nodes,links)
            if len(group)>=threshold]

def check_all_partitions(nodes):
    edges=list(combinations(range(nodes),2))
    configurations=0
    for flags in range(1<<len(edges)):
        live_links=[e for i,e in enumerate(edges) if flags & (1<<i)]
        active=eligible_majority_components(nodes,live_links)
        if len(active)>1:
            raise AssertionError(f"multiple majority groups: {active}")
        configurations+=1
    return configurations

if __name__=="__main__":
    assert check_all_partitions(3)==8
    assert check_all_partitions(5)==1024
    assert eligible_majority_components(3,[(0,1)])==[frozenset({0,1})]
    assert eligible_majority_components(3,[])==[]
    print("PASS: every undirected graph of 3 or 5 members has at most one majority component")
