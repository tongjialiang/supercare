from common_utils import DEFAULT_GRAPH_PATH, load_graph, tool_用药洞察
from tests.test_helper import run_tool_case

if __name__ == "__main__":
    print(run_tool_case("用药洞察", tool_用药洞察, load_graph(DEFAULT_GRAPH_PATH)))
