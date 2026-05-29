from common_utils import DEFAULT_GRAPH_PATH, load_graph, tool_基础信息
from tests.test_helper import run_tool_case

if __name__ == "__main__":
    print(run_tool_case("基础信息", tool_基础信息, load_graph(DEFAULT_GRAPH_PATH)))
