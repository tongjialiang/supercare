from common_utils import DEFAULT_GRAPH_PATH, load_graph, tool_个性化健康档案
from tests.test_helper import run_tool_case

if __name__ == "__main__":
    print(run_tool_case("个性化健康档案", tool_个性化健康档案, load_graph(DEFAULT_GRAPH_PATH)))
