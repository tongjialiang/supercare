from common_utils import DEFAULT_GRAPH_PATH, load_graph, tool_体征洞察
from tests.test_helper import run_tool_case

if __name__ == "__main__":
    print(run_tool_case("体征洞察", tool_体征洞察, load_graph(DEFAULT_GRAPH_PATH)))
