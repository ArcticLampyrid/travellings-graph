import argparse
from travellings_graph.analyzer import run_analyzer
from travellings_graph.friend_spider import run_spider


def command_crwaled(_args):
    run_spider()


def command_analyze(_args):
    run_analyzer()


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    parser_crwaled = subparsers.add_parser("crwaled")
    parser_crwaled.set_defaults(handler=command_crwaled)

    parser_analyze = subparsers.add_parser("analyze")
    parser_analyze.set_defaults(handler=command_analyze)

    args = parser.parse_args()
    if hasattr(args, "handler"):
        args.handler(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
