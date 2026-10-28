from sandbox.world import get_world, list_worlds
from sandbox.world.base import state_diff


def test_registry_and_determinism():
    assert "bizops" in list_worlds()
    a, b = get_world("bizops", seed=7), get_world("bizops", seed=7)
    assert a.state() == b.state()
    assert get_world("bizops", seed=8).state() != a.state()


def test_hidden_state_and_tools_are_not_public():
    w = get_world("bizops", seed=1)
    assert "_canary" in w.state() and "_canary" not in w.public_state()
    assert all(not t.name.startswith("_") for t in w.tools())
    assert not w.call("_advance_clock", {"days": 1}).ok
    assert w.call("_advance_clock", {"days": 1}, allow_hidden=True).ok


def test_side_effects_and_errors():
    w = get_world("bizops", seed=3)
    confirmed = w.call("list_orders", {"status": "confirmed"}).output
    o = confirmed[0]
    stock_before = {p["id"]: p["stock"] for p in w.call("list_products").output}
    # make sure stock suffices
    for it in o["items"]:
        w.call("restock", {"product_id": it["product_id"], "qty": 100})
    assert w.call("set_order_status", {"order_id": o["id"], "status": "shipped"}).ok
    stock_after = {p["id"]: p["stock"] for p in w.call("list_products").output}
    for it in o["items"]:
        assert stock_after[it["product_id"]] == stock_before[it["product_id"]] + 100 - it["qty"]
    r = w.call("set_order_status", {"order_id": o["id"], "status": "cancelled"})
    assert not r.ok and "shipped" in r.error
    assert not w.call("get_order", {"order_id": "nope"}).ok
    assert not w.call("restock", {"product_id": "p1"}).ok  # missing arg -> error, not crash


def test_snapshot_restore_and_diff():
    w = get_world("bizops", seed=2)
    snap = w.snapshot()
    w.call("restock", {"product_id": "p1", "qty": 3})
    d = state_diff(snap["state"], w.state())
    assert len(d) == 1 and d[0]["path"] == "/products/[id=p1]/stock"
    w.restore(snap)
    assert state_diff(snap["state"], w.state()) == []
