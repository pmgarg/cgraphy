def pagerank(edges, nodes, damping=0.85, iterations=30):
    if not nodes:
        return {}
    n = len(nodes)
    out_weight = {}
    targets = {}
    for s, t, w in edges:
        out_weight[s] = out_weight.get(s, 0.0) + w
        targets.setdefault(s, []).append((t, w))
    rank = {v: 1.0 / n for v in nodes}
    base = (1.0 - damping) / n
    for _ in range(iterations):
        nxt = {v: base for v in nodes}
        dangling = sum(rank[v] for v in nodes if v not in targets)
        share = damping * dangling / n
        for v in nodes:
            nxt[v] += share
        for s, outs in targets.items():
            rs = damping * rank.get(s, 0.0)
            ow = out_weight[s]
            for t, w in outs:
                if t in nxt:
                    nxt[t] += rs * w / ow
        rank = nxt
    mx = max(rank.values())
    return {v: (r / mx if mx > 0 else 0.0) for v, r in rank.items()}


def apply_pagerank(db):
    nodes = db.all_node_ids()
    edges = [(e["source_id"], e["target_id"], e["weight"])
             for e in db.all_edges() if e["kind"] != "contains"]
    db.set_ranks(pagerank(edges, nodes))
    db.commit()
