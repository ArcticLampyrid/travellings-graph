from dataclasses import dataclass
import json
import os
import sys
import urllib3
import urllib3.util
import networkx as nx
from travellings_graph.member_list import MemberRecord, read_members
from travellings_graph.friend_spider import run_spider


@dataclass
class ConnectionAnalysis:
    name: str
    url: str
    n_connected: int
    avg_distance: float


def simple_host(url: str | urllib3.util.Url | None) -> str:
    if url is None:
        return ""
    if isinstance(url, str):
        url = urllib3.util.parse_url(url)
    if url.host is None:
        return ""
    return url.host.removeprefix("www.").removeprefix("blog.")


def build_graph(members: list[MemberRecord]) -> nx.DiGraph:
    member_map = {simple_host(member.url): member for member in members}
    graph = nx.DiGraph()
    for member in members:
        graph.add_node(member.id, name=member.name)
    with open("friends.lines.json", "r", encoding="utf-8") as f:
        while line := f.readline():
            record = json.loads(line)
            if record["kind"] == "friends_link":
                source = simple_host(record["start"])
                target = simple_host(record["target"])
                if source == target:
                    continue
                if source in member_map and target in member_map:
                    source_member = member_map[source]
                    target_member = member_map[target]
                    graph.add_edge(source_member.id, target_member.id)
    return graph


def analyze_connection(
    graph: nx.DiGraph, members: list[MemberRecord]
) -> list[ConnectionAnalysis]:
    member_map_id = {member.id: member for member in members}
    analysis_result: list[ConnectionAnalysis] = []
    paths = nx.all_pairs_shortest_path_length(graph)
    for target, sources in paths:
        target_member = member_map_id[target]
        if len(sources) == 1:
            analysis_result.append(
                ConnectionAnalysis(
                    name=target_member.name,
                    url=target_member.url,
                    n_connected=0,
                    avg_distance=0,
                )
            )
            continue
        connected_edges = len(sources) - 1
        avg_distance = sum(sources.values()) / connected_edges
        analysis_result.append(
            ConnectionAnalysis(
                name=target_member.name,
                url=target_member.url,
                n_connected=connected_edges,
                avg_distance=avg_distance,
            )
        )
    analysis_result.sort(
        key=lambda x: (
            x.n_connected / x.avg_distance if x.avg_distance > 0 else 0,
            x.name,
        )
    )
    return analysis_result


def main():
    if "--crwaled" in sys.argv:
        run_spider()
        return

    if not os.path.exists("friends.lines.json"):
        print("Friends Info is not crwaled yet, please run with `--crwaled` first")
        sys.exit(1)

    members = read_members()
    graph = build_graph(members)

    nx.write_gexf(graph, "graph.gexf")

    connected_to = analyze_connection(graph, members)
    with open("connected_to.md", "w", encoding="utf-8") as f:
        for analysis in connected_to:
            f.write(f"- [{analysis.name}]({analysis.url}) ")
            f.write(f"is connected to {analysis.n_connected} nodes, ")
            f.write(f"avg. distance {analysis.avg_distance:.2f}\n")
    with open("connected_to.csv", "w", encoding="utf-8") as f:
        f.write("Name,URL,ConnectedTo,AvgDistance\n")
        for analysis in connected_to:
            f.write(f'"{analysis.name}",')
            f.write(f'"{analysis.url}",')
            f.write(f"{analysis.n_connected},")
            f.write(f"{analysis.avg_distance:.2f}\n")

    connected_by = analyze_connection(graph.reverse(), members)
    with open("connected_by.md", "w", encoding="utf-8") as f:
        for analysis in connected_by:
            f.write(f"- [{analysis.name}]({analysis.url}) ")
            f.write(f"is connected by {analysis.n_connected} nodes, ")
            f.write(f"avg. distance {analysis.avg_distance:.2f}\n")
    with open("connected_by.csv", "w", encoding="utf-8") as f:
        f.write("Name,URL,ConnectedBy,AvgDistance\n")
        for analysis in connected_by:
            f.write(f'"{analysis.name}",')
            f.write(f'"{analysis.url}",')
            f.write(f"{analysis.n_connected},")
            f.write(f"{analysis.avg_distance:.2f}\n")


if __name__ == "__main__":
    main()
