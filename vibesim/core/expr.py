"""Safe arithmetic/boolean expressions over entity state, e.g. `cpu_pct > 90 or memory_pct > 95`.

Only whitelisted syntax and functions compile; no attribute access, subscripts or builtins.
"""

import ast
import math
from collections.abc import Mapping
from typing import Any

FUNCTIONS: dict[str, Any] = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "sin": math.sin,
    "cos": math.cos,
    "pi": math.pi,
    "clamp": lambda x, lo, hi: max(lo, min(hi, x)),
}

ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.BoolOp,
    ast.Compare,
    ast.IfExp,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.operator,
    ast.unaryop,
    ast.boolop,
    ast.cmpop,
)


MAX_EXPONENT = 10


def _is_unbounded(node: ast.BinOp) -> bool:
    """Block the two ways a tiny expression can eat CPU or memory: huge powers and string repetition."""
    if isinstance(node.op, ast.Pow):
        exp = node.right
        return not (
            isinstance(exp, ast.Constant) and isinstance(exp.value, int | float) and abs(exp.value) <= MAX_EXPONENT
        )
    return any(isinstance(side, ast.Constant) and isinstance(side.value, str) for side in (node.left, node.right))


class Expr:
    def __init__(self, source: str):
        tree = ast.parse(source, mode="eval")
        for node in ast.walk(tree):
            if not isinstance(node, ALLOWED_NODES):
                raise ValueError(f"'{source}': {type(node).__name__} is not allowed in expressions")
            if isinstance(node, ast.Call) and not (isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS):
                raise ValueError(f"'{source}': only these functions are allowed: {sorted(FUNCTIONS)}")
            if isinstance(node, ast.BinOp) and _is_unbounded(node):
                raise ValueError(f"'{source}': exponents must be literals up to {MAX_EXPONENT}; no string arithmetic")
        self.source = source
        self.names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - FUNCTIONS.keys()
        self._code = compile(tree, "<expr>", "eval")

    def __call__(self, env: Mapping[str, Any]) -> Any:
        # safe: the tree was whitelisted above and builtins are stripped
        return eval(self._code, {"__builtins__": {}, **FUNCTIONS}, dict(env))
