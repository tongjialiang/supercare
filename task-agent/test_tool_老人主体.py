from common_utils import DEFAULT_GRAPH_PATH, load_graph, tool_老人主体
from tests.test_helper import run_tool_case

if __name__ == "__main__":
    print(run_tool_case("老人主体", tool_老人主体, load_graph(DEFAULT_GRAPH_PATH)))
