"""Write docs/reference/config.md from the Pydantic models, so the reference can't drift from the code.

python scripts/gen_reference.py
"""

import json
import typing
from pathlib import Path

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from vibesim.core import state

MODELS: list[type[BaseModel]] = [
    state.SimulationConfig,
    state.EntityConfig,
    state.Drift,
    state.MeanRevert,
    state.Cycle,
    state.Derived,
    state.Transition,
    state.PluginRef,
    state.ChaosRules,
    state.Anomaly,
    state.TimelineStep,
    state.RandomChaos,
    state.Persistence,
    state.Outputs,
    state.MqttOutput,
    state.OtlpOutput,
    state.TelemetryEvent,
]
OUT = Path(__file__).resolve().parent.parent / "docs" / "reference" / "config.md"


def type_name(annotation: object) -> str:
    args = typing.get_args(annotation)
    if typing.get_origin(annotation) is dict and args and typing.get_origin(args[1]) is typing.Annotated:
        return "dict[str, FieldSpec]"  # FieldSpec = drift | mean_revert | cycle | derived
    text = str(annotation).replace("typing.", "").replace("vibesim.core.state.", "")
    return text.replace("<class '", "").replace("'>", "").replace("datetime.datetime", "datetime")


def render() -> str:
    lines = [
        "# Config reference",
        "",
        "Generated from the Pydantic models by `scripts/gen_reference.py`. Do not edit by hand.",
        "",
    ]
    for model in MODELS:
        lines += [f"## {model.__name__}", ""]
        if model.__doc__:
            lines += [" ".join(model.__doc__.split()), ""]
        lines += ["| Field | Type | Default |", "|---|---|---|"]
        for name, info in model.model_fields.items():
            if info.default_factory is not None:
                default = "generated"
            elif info.default is PydanticUndefined:
                default = "**required**"
            else:
                default = f"`{json.dumps(info.default, default=str)}`"
            kind = type_name(info.annotation).replace("|", "\\|")  # a bare | would split the table cell
            lines.append(f"| `{name}` | `{kind}` | {default} |")
        lines.append("")
    schema = json.dumps(state.SimulationConfig.model_json_schema(), indent=2)
    lines += ["## JSON Schema", "", "```json", schema, "```", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    OUT.write_text(render())
    print(f"wrote {OUT}")
