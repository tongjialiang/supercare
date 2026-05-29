from common_utils import DEFAULT_GRAPH_PATH, load_graph, tool_风险洞察
from tests.test_helper import run_tool_case

if __name__ == "__main__":
    print(run_tool_case("风险洞察", tool_风险洞察, load_graph(DEFAULT_GRAPH_PATH)))
