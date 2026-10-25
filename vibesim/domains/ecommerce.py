"""Online-store preset: traffic, conversion, orders, revenue and inventory with restocking. Pure config."""

from vibesim.core.state import Cycle, Derived, EntityConfig, MeanRevert, Transition

DAY_S = 86_400
SELLING = "(1 if inventory > 0 else 0)"


def store(
    id: str, *, count: int = 1, visitors_per_min: float = 60.0, conversion_pct: float = 3.0, avg_order: float = 42.0
) -> EntityConfig:
    return EntityConfig(
        id=id,
        type="store",
        count=count,
        initial_state={
            "avg_order_value": avg_order,
            "inventory": 500.0,
            "orders_total": 0.0,
            "revenue_total": 0.0,
            "signups_total": 0.0,
            "status": "in_stock",
        },
        fields={
            "visitors_per_min": Cycle(
                behavior="cycle",
                base=visitors_per_min,
                amplitude=visitors_per_min / 2,
                period_s=DAY_S,
                noise=visitors_per_min / 10,
                min=0,
                round=1,
            ),
            "conversion_pct": MeanRevert(
                behavior="mean_revert", target=conversion_pct, noise=0.2, min=0, max=100, round=2
            ),
            "payment_failure_pct": MeanRevert(behavior="mean_revert", target=1.5, noise=0.2, min=0, max=100, round=2),
            "orders_per_min": Derived(
                behavior="derived", expr=f"visitors_per_min * conversion_pct / 100 * {SELLING}", round=2
            ),
            "orders_total": Derived(
                behavior="derived",
                expr="orders_total + orders_per_min * (1 - payment_failure_pct / 100) * dt / 60",
                round=2,
            ),
            "revenue_total": Derived(
                behavior="derived",
                expr="revenue_total + orders_per_min * (1 - payment_failure_pct / 100) * avg_order_value * dt / 60",
                round=2,
            ),
            "signups_total": Derived(
                behavior="derived", expr="signups_total + visitors_per_min * 0.01 * dt / 60", round=2
            ),
            "inventory": Derived(
                behavior="derived",
                expr="inventory - orders_per_min * dt / 60 + (5 * dt if status == 'restocking' else 0)",
                min=0,
                round=2,
            ),
        },
        machine=[
            Transition(source="in_stock", target="low_stock", when="inventory < 100"),
            Transition(source=["in_stock", "low_stock"], target="out_of_stock", when="inventory <= 0"),
            Transition(source=["low_stock", "out_of_stock"], target="restocking", p=0.05),
            Transition(source="restocking", target="in_stock", when="inventory >= 400"),
        ],
    )
