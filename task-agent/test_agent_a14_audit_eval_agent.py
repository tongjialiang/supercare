from pathlib import Path
from agent_a14_audit_eval_agent import SPEC, run_agent
from common_utils import DEFAULT_GRAPH_PATH, TOOL_PURPOSE
from tests.test_helper import run_agent_case

if __name__ == "__main__":
    desc = "\n".join([f"{name}:{TOOL_PURPOSE.get(name,'')}" for name in SPEC.tool_names])
    prompt = (
        "请对本次 TaskAgent 输出的各类报告内容进行审计评估：检查字段是否完整、是否出现关键信息缺失、是否存在编造风险、"
        "是否按要求区分历史图谱参考与用户最新输入；并在报告中给出改进建议。"
        "同时请结合测试中 use_tools=true 与 use_tools=false 的对照结果，论证工具使用对输出准确性、完整性与专业性的提升作用。"
    )
    print(run_agent_case("a14_audit_eval", run_agent, prompt, Path(DEFAULT_GRAPH_PATH), desc))
