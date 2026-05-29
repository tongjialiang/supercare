from common_utils import DEFAULT_GRAPH_PATH, load_graph, tool_睡眠记录
from tests.test_helper import run_tool_case

if __name__ == "__main__":
    print(run_tool_case("睡眠记录", tool_睡眠记录, load_graph(DEFAULT_GRAPH_PATH)))
