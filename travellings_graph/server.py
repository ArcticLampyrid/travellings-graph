import asyncio
import csv
from typing import Optional
from attr import dataclass
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import networkx as nx
from hypercorn.config import Config
from hypercorn.asyncio import serve
from pydantic import BaseModel
from travellings_graph.domain_utils import strip_host


class AnalysisItem(BaseModel):
    id: int
    name: str
    url: str
    links: str
    outgoing_count: int
    outgoing_count_in6degrees: int
    outgoing_average_distance: float
    incoming_count: int
    incoming_count_in6degrees: int
    incoming_average_distance: float


class GetAnalysisAllResponse(BaseModel):
    total: int
    items: list[AnalysisItem]


class GetAnalysisByPageResponse(BaseModel):
    total_items: int
    total_page: int
    page: int
    items: list[AnalysisItem]


class BlogBrief(BaseModel):
    id: int
    name: str
    url: str


class GetShortestPathsResponse(BaseModel):
    source_id: int
    target_id: int
    distance: int
    nodes: list[BlogBrief]
    paths: list[list[int]]


class GetShortestPathsNotFoundResponse(BaseModel):
    detail: str


class GetSuccessorsResponse(BaseModel):
    source_id: int
    nodes: list[BlogBrief]


class GetPredecessorsResponse(BaseModel):
    target_id: int
    nodes: list[BlogBrief]


@dataclass
class GlobalData:
    analysis: list[AnalysisItem]
    analysis_id_map: dict[int, AnalysisItem]
    analysis_host_map: dict[str, AnalysisItem]
    graph: nx.DiGraph


def reload() -> GlobalData:
    analysis: list[AnalysisItem] = []
    with open("analysis.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            analysis.append(
                AnalysisItem(
                    id=int(row["ID"]),
                    name=row["Name"],
                    url=row["URL"],
                    links=row["Links"],
                    outgoing_count=int(row["OutgoingCount"]),
                    outgoing_count_in6degrees=int(row["OutgoingCountIn6Degrees"]),
                    outgoing_average_distance=float(row["OutgoingAverage"]),
                    incoming_count=int(row["IncomingCount"]),
                    incoming_count_in6degrees=int(row["IncomingCountIn6Degrees"]),
                    incoming_average_distance=float(row["IncomingAverage"]),
                )
            )

    analysis_id_map = {item.id: item for item in analysis}
    analysis_host_map = {strip_host(item.url): item for item in analysis}

    graph = nx.read_gexf("graph.gexf", node_type=int)
    if not isinstance(graph, nx.DiGraph):
        raise ValueError("Invalid graph type")

    return GlobalData(
        analysis=analysis,
        analysis_id_map=analysis_id_map,
        analysis_host_map=analysis_host_map,
        graph=graph,
    )


global_data: GlobalData = GlobalData([], {}, {}, nx.DiGraph())
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/analysis")
def get_analysis_all() -> GetAnalysisAllResponse:
    return GetAnalysisAllResponse(
        total=len(global_data.analysis),
        items=global_data.analysis,
    )


@app.get("/v1/analysis/page/{page}")
def get_analysis_by_page(page: int, q: str | None = None) -> GetAnalysisByPageResponse:
    data = global_data.analysis
    if q is not None:
        q = q.lower()
        data = [
            item
            for item in data
            if q in str(item.id)
            or q in item.name.lower()
            or q in item.url.lower()
            or q in item.links.lower()
        ]
    item_per_page = 32
    total_page = (len(data) + item_per_page - 1) // item_per_page
    items = data[(page - 1) * item_per_page : page * item_per_page]
    return GetAnalysisByPageResponse(
        total_items=len(data),
        total_page=total_page,
        page=page,
        items=items,
    )


def try_get_node_id(node: str) -> Optional[int]:
    try:
        node_id = int(node, base=10)
        if node_id in global_data.analysis_id_map:
            return node_id
    except ValueError:
        host = strip_host(node)
        item = global_data.analysis_host_map.get(host)
        if item is not None:
            return item.id
    return None


@app.get(
    "/v1/shortest-paths/{source}/{target}",
    response_model=GetShortestPathsResponse,
    responses={404: {"model": GetShortestPathsNotFoundResponse}},
)
def get_shortest_paths(
    source: str, target: str
) -> GetShortestPathsResponse | JSONResponse:
    source_id = try_get_node_id(source)
    target_id = try_get_node_id(target)
    if source_id is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Source not found",
            },
        )
    if target_id is None:
        return JSONResponse(
            status_code=404,
            content={
                "detail": "Target not found",
            },
        )
    try:
        paths = list(nx.all_shortest_paths(global_data.graph, source_id, target_id))
        nodes = []
        node_set = set()
        for path in paths:
            for node_id in path:
                if node_id not in node_set:
                    node_set.add(node_id)
                    node = global_data.analysis_id_map[node_id]
                    nodes.append(
                        BlogBrief(
                            id=node.id,
                            name=node.name,
                            url=node.url,
                        )
                    )
        return GetShortestPathsResponse(
            source_id=source_id,
            target_id=target_id,
            distance=len(paths[0]) - 1,
            nodes=nodes,
            paths=paths,
        )
    except nx.NetworkXNoPath:
        source_node_brief = BlogBrief(
            id=source_id,
            name=global_data.analysis_id_map[source_id].name,
            url=global_data.analysis_id_map[source_id].url,
        )
        target_node_brief = BlogBrief(
            id=target_id,
            name=global_data.analysis_id_map[target_id].name,
            url=global_data.analysis_id_map[target_id].url,
        )
        return GetShortestPathsResponse(
            source_id=source_id,
            target_id=target_id,
            distance=-1,
            nodes=[source_node_brief, target_node_brief],
            paths=[],
        )


@app.get("/v1/successors/{source_id}")
def get_successors(source_id: int) -> GetSuccessorsResponse:
    try:
        successors = list(global_data.graph.successors(source_id))
        nodes = []
        for node_id in successors:
            node = global_data.analysis_id_map[node_id]
            nodes.append(
                BlogBrief(
                    id=node.id,
                    name=node.name,
                    url=node.url,
                )
            )
        return GetSuccessorsResponse(
            source_id=source_id,
            nodes=nodes,
        )
    except nx.NetworkXError:
        return GetSuccessorsResponse(
            source_id=source_id,
            nodes=[],
        )


@app.get("/v1/predecessors/{target_id}")
def get_predecessors(target_id: int) -> GetPredecessorsResponse:
    try:
        predecessors = list(global_data.graph.predecessors(target_id))
        nodes = []
        for node_id in predecessors:
            node = global_data.analysis_id_map[node_id]
            nodes.append(
                BlogBrief(
                    id=node.id,
                    name=node.name,
                    url=node.url,
                )
            )
        return GetPredecessorsResponse(
            target_id=target_id,
            nodes=nodes,
        )
    except nx.NetworkXError:
        return GetPredecessorsResponse(
            target_id=target_id,
            nodes=[],
        )


def run_server(bind: Optional[list[str]] = None):
    global global_data  # pylint: disable=global-statement
    global_data = reload()
    config = Config()
    config.bind = bind or [":8471"]
    asyncio.run(serve(app, config))  # type: ignore


if __name__ == "__main__":
    run_server()
