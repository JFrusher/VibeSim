"""Run the VibeSim server: python -m vibesim [--host HOST] [--port PORT]"""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(prog="vibesim")
    parser.add_argument("--host", default="127.0.0.1", help="bind address; localhost-only by default")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("vibesim.transport.rest:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
