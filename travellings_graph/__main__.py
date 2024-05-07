import argparse
from travellings_graph.analyzer import run_analyzer
from travellings_graph.friend_spider import run_spider
from travellings_graph.server import run_server


def command_crwaled(_args):
    run_spider()


def command_analyze(_args):
    run_analyzer()


def command_serve(args):
    run_server(args.bind)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_crwaled = subparsers.add_parser("crwaled")
    parser_crwaled.set_defaults(handler=command_crwaled)

    parser_analyze = subparsers.add_parser("analyze")
    parser_analyze.set_defaults(handler=command_analyze)

    parser_serve = subparsers.add_parser("serve")
    parser_serve.add_argument("--bind", nargs="*", default=[":8471"])
    parser_serve.set_defaults(handler=command_serve)

    args = parser.parse_args()
    if hasattr(args, "handler"):
        args.handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
