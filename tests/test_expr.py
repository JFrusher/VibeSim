import pytest

from vibesim.core.expr import Expr


@pytest.mark.parametrize(
    ("source", "env", "expected"),
    [
        ("40 * (1 + cpu / 100) ** 3", {"cpu": 100}, 320),
        ("cpu > 90 or mem > 95", {"cpu": 10, "mem": 96}, True),
        ("status in ('en_route', 'delayed')", {"status": "delayed"}, True),
        ("clamp(x, 0, 10)", {"x": 42}, 10),
        ("'hot' if temp > 30 else 'ok'", {"temp": 31}, "hot"),
    ],
)
def test_evaluates(source, env, expected):
    assert Expr(source)(env) == expected


def test_collects_names_but_not_functions():
    assert Expr("max(a, b) + sqrt(c)").names == {"a", "b", "c"}


@pytest.mark.parametrize(
    "source",
    [
        "__import__('os')",
        "x.__class__",
        "x[0]",
        "open('f')",
        "(lambda: 1)()",
        "9 ** 9 ** 9",
        "x ** y",
        "'a' * 10",
    ],
)
def test_rejects_unsafe(source):
    with pytest.raises(ValueError):
        Expr(source)
