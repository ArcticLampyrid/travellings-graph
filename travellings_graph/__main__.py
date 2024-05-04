from dataclasses import dataclass
import datetime
import json
import os
import sys
from typing import Generator
import urllib3
import urllib3.util
import networkx as nx
from travellings_graph.member_list import MemberRecord, read_members
from travellings_graph.friend_spider import run_spider


@dataclass
class ConnectionAnalysis:
    id: int
    connection_count: int
    avg_distance: float
    connection_in6degrees: int = 0


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


def analyze_connection(graph: nx.DiGraph) -> Generator[ConnectionAnalysis, None, None]:
    paths = nx.all_pairs_shortest_path_length(graph)
    for target, sources in paths:
        if len(sources) == 1:
            yield ConnectionAnalysis(
                id=target,
                connection_count=0,
                avg_distance=0,
            )
            continue
        connected_edges = len(sources) - 1
        avg_distance = sum(sources.values()) / connected_edges
        connection_in6degrees = (
            sum(map(lambda x: 1 if x <= 6 else 0, sources.values())) - 1
        )
        yield ConnectionAnalysis(
            id=target,
            connection_count=connected_edges,
            avg_distance=avg_distance,
            connection_in6degrees=connection_in6degrees,
        )


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

    outgoing_connections = {
        connection.id: connection for connection in analyze_connection(graph)
    }
    incoming_connections = {
        connection.id: connection for connection in analyze_connection(graph.reverse())
    }

    with open("analysis.csv", "w", encoding="utf-8") as f:
        f.write("ID,Name,URL," +
                "OutgoingCount,OutgoingCountIn6Degrees,OutgoingAverage," + 
                "IncomingCount,IncomingCountIn6Degrees,IncomingAverage\n")
        for member in members:
            outgoing = outgoing_connections[member.id]
            incoming = incoming_connections[member.id]
            f.write(
                f"{member.id},\"{member.name}\",\"{member.url}\"," +
                f"{outgoing.connection_count}," +
                f"{outgoing.connection_in6degrees}," +
                f"{outgoing.avg_distance:.4f}," +
                f"{incoming.connection_count}," +
                f"{incoming.connection_in6degrees}," +
                f"{incoming.avg_distance:.4f}\n"
            )


    with open("analysis.md", "w", encoding="utf-8") as f:
        f.write("# Connection Analysis\n")
        f.write(
            f"Build Date: {datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}  \n"
        )
        f.write(f"Total members: {len(members)}  \n")
        f.write(f"Total connections: {len(graph.edges)}  \n")
        f.write(
            f"Average connections per member: {len(graph.edges) / len(members)}  \n"
        )
        for member in members:
            outgoing = outgoing_connections[member.id]
            incoming = incoming_connections[member.id]
            f.write(f"## [{member.name}]({member.url}) \\(Member #{member.id}\\)\n")
            f.write("### Outgoing Connections\n")
            f.write(f"Connected to {outgoing.connection_count} members")
            f.write(f" ({outgoing.connection_in6degrees} in 6 degrees)  \n")
            f.write(f"Average distance: {outgoing.avg_distance:.4f}  \n")
            f.write("### Incoming Connections\n")
            f.write(f"Connected by {incoming.connection_count} members")
            f.write(f" ({incoming.connection_in6degrees} in 6 degrees)  \n")
            f.write(f"Average distance: {incoming.avg_distance:.4f}  \n")


if __name__ == "__main__":
    main()
