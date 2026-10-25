"""vibesim command line: run, compile, replay, serve."""

import argparse
import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

import uvicorn

from vibesim.core.compiler import Compiler, compile_with
from vibesim.core.engine import Engine, simulations
from vibesim.core.state import SimulationConfig
from vibesim.scenario import dump_scenario, load_scenario

SCENARIO_SUFFIXES = (".yaml", ".yml", ".json")


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    args.handler(args)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="vibesim", description="Promptable local-first simulations.")
    root.set_defaults(handler=lambda a: serve(a))
    _server_flags(root)
    commands = root.add_subparsers(title="commands")

    run = commands.add_parser("run", help="start the server with a simulation from a prompt or scenario file")
    run.add_argument("source", help='a prompt ("5 vans in rainy Bristol") or a .yaml/.json scenario file')
    _compile_flags(run)
    _server_flags(run)
    run.set_defaults(handler=lambda a: serve(a, lambda: Engine(config_from(a.source, a.compiler, a.seed))))

    compile_ = commands.add_parser("compile", help="print the scenario a prompt compiles to")
    compile_.add_argument("prompt")
    _compile_flags(compile_)
    compile_.add_argument("--format", choices=("yaml", "json"), default="yaml")
    compile_.set_defaults(
        handler=lambda a: print(dump_scenario(compile_with(a.compiler, a.prompt, a.seed), a.format), end="")
    )

    replay = commands.add_parser("replay", help="serve a recorded run")
    replay.add_argument("recording_id")
    replay.add_argument("--speed", type=float, default=1.0)
    _server_flags(replay)
    replay.set_defaults(handler=lambda a: serve(a, lambda: _replay(a.recording_id, a.speed)))

    serve_ = commands.add_parser("serve", help="start the server with no simulation")
    _server_flags(serve_)
    serve_.set_defaults(handler=lambda a: serve(a))
    return root


def config_from(source: str, compiler: str, seed: int) -> SimulationConfig:
    if source.endswith(SCENARIO_SUFFIXES):
        if not Path(source).exists():
            raise SystemExit(f"vibesim: no scenario file '{source}'")
        return load_scenario(source)
    return compile_with(cast(Compiler, compiler), source, seed)  # argparse already limited the choices


def serve(args: argparse.Namespace, make_engine: Callable[[], Engine] | None = None) -> None:
    from vibesim.transport.rest import app

    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=args.port))

    async def run() -> None:
        task = asyncio.create_task(server.serve())
        while not server.started:
            if task.done():
                return await task  # startup failed (e.g. port in use); surface uvicorn's error
            await asyncio.sleep(0.05)
        base = f"http://{args.host}:{args.port}"
        if make_engine:
            try:
                engine = await asyncio.to_thread(make_engine)
            except ValueError as e:
                server.should_exit = True
                await task
                raise SystemExit(f"vibesim: {e}") from e
            sid = engine.config.simulation_id
            simulations[sid] = engine
            engine.start()
            print(f"\n  simulation  {sid} ({engine.config.domain}, {len(engine.state.entities)} entities)")
            print(f"  console     {base}/?sim={sid}")
            print(f"  stream      {base}/simulations/{sid}/stream")
            print(f"  websocket   ws://{args.host}:{args.port}/simulations/{sid}/ws\n", flush=True)
        else:
            print(f"\n  console     {base}/\n", flush=True)
        await task

    asyncio.run(run())


def _replay(recording_id: str, speed: float) -> Engine:
    from vibesim.replay import ReplayEngine

    return ReplayEngine(recording_id, speed)


def _compile_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--compiler", choices=("keyword", "claude"), default="keyword")
    p.add_argument("--seed", type=int, default=0)


def _server_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--host", default="127.0.0.1", help="bind address; localhost-only by default")
    p.add_argument("--port", type=int, default=8000)


if __name__ == "__main__":
    main(sys.argv[1:])
