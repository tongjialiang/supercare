from common_utils import DEFAULT_GRAPH_PATH, load_graph, tool_近况摘要
from tests.test_helper import run_tool_case

if __name__ == "__main__":
    print(run_tool_case("近况摘要", tool_近况摘要, load_graph(DEFAULT_GRAPH_PATH)))
