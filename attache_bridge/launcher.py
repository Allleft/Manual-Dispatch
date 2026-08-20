import argparse
import os

import uvicorn

from attache_bridge.config import (
    AttacheBridgeConfig,
    AttacheBridgeConfigurationError,
)
from attache_bridge.main import app


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787


def _host_argument(value):
    host = str(value or "").strip()
    if not host or any(character.isspace() or ord(character) < 32 for character in host):
        raise argparse.ArgumentTypeError("host must not be empty or contain whitespace")
    return host


def _port_argument(value):
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("port must be an integer") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def create_argument_parser():
    parser = argparse.ArgumentParser(
        prog="attache-bridge",
        description="Run the read-only Attaché invoice bridge.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        type=_host_argument,
        help=f"bind host (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        default=DEFAULT_PORT,
        type=_port_argument,
        help=f"bind port (default: {DEFAULT_PORT})",
    )
    return parser


def parse_arguments(argv=None):
    return create_argument_parser().parse_args(argv)


def main(argv=None, *, environ=None, run_server=None, output=None):
    args = parse_arguments(argv)
    environment = os.environ if environ is None else environ
    write_line = print if output is None else output
    serve = uvicorn.run if run_server is None else run_server

    try:
        config = AttacheBridgeConfig.from_environment(environment)
    except AttacheBridgeConfigurationError:
        write_line("Attache Bridge")
        write_line("Bridge configuration is invalid.")
        return 2

    write_line("Attache Bridge")
    write_line(f"Listening: http://{args.host}:{args.port}")
    write_line(
        "ODBC configuration present: "
        + ("yes" if bool(config.connection_string) else "no")
    )
    write_line(
        "Bridge token configured: "
        + ("yes" if bool(config.api_token) else "no")
    )

    serve(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
