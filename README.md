# Travellings Graph
Have you ever heard of Six Degrees of Separation? Six degrees of separation is the idea that all people are six or fewer social connections away from each other. As a result, a chain of "friend of a friend" statements can be made to connect any two people in a maximum of six steps.

This project is to build a graph of links between [Travellings](https://www.travellings.cn/) members, and analyze the connections between them, showing how many steps in average are needed to connect to/by each member.

## Usage
```bash
docker buildx build -t travellings-graph .
mkdir -p data
docker run --rm -v $(pwd)/data:/app/data travellings-graph crwaled
docker run --rm -v $(pwd)/data:/app/data travellings-graph analyze
ls -l data
```

## Crwal
You can run with subcommand `crwaled` to crwal the data from the source.

> [!WARNING]  
> Because there are no standard format for exchanging Links, the data is crwaled with many tricks, and may not be accurate. If you find any error, please let me know.

The member list is from [Travellings List](https://list.travellings.cn/), and saved in `data/members.json`.  
The Links data is crwaled from each member's Links page, and saved in `data/friends.lines.json`.

## Analyze
You can run with subcommand `analyze` to analyze the data.

During the analysis, the graph is firstly built with [NetworkX](https://networkx.org/), and saved in `data/graph.gexf`. All nodes are labeled with their Member ID in [Travellings List](https://list.travellings.cn/).

> [!TIP]  
> You can use [Gephi](https://gephi.org/) to visualize the graph and analyze the connections. For Arch Linux, you can install Gephi with `pacman -S gephi`.

Also, a basic analysis is generated and saved in `data/analysis.csv`, as well as a simple report in `data/analysis.md`. The results include the average steps needed to connect to/by each member.

## Results
A copy of the completed data was shared on my blog \([view it](https://alampy.com/2024/05/02/test-six-degrees-of-separation-on-travellings/)\). Note that the data may be outdated, and the results may be different from the latest.

## License
Licensed under the [MIT License](LICENSE).
