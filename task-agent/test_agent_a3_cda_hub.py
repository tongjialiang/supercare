from pathlib import Path
from agent_a3_cda_hub import SPEC, run_agent
from common_utils import DEFAULT_GRAPH_PATH, TOOL_PURPOSE
from tests.test_helper import run_agent_case

if __name__ == "__main__":
    desc = "\n".join([f"{name}:{TOOL_PURPOSE.get(name,'')}" for name in SPEC.tool_names])
    prompt = (
        "上海籍失智老人陈女士返院一周，老人有阿尔茨海默病性痴呆病史，曾植入心脏起搏器、行胆囊切除术，"
        "头部外伤后恢复中，伴有血压偏高、血脂异常，存在拒绝配合康复的BPSD症状，家属有明显长期照护焦虑。"
        "提供一周综合报告（照护中重点落实跌倒防护、规律服药，尝试结合其跳舞喜好进行认知干预，但老人配合度仍较低，"
        "家属焦虑未明显缓解）及护理结论（建议加强精神科干预，优化认知干预方案，同步为家属提供照护指导），"
        "测试智能体是否能给出准确GP确认意见，制定精神科会诊决策，更新照护目标，协调多方协同照护。"
    )
    print(run_agent_case("a3_cda_hub", run_agent, prompt, Path(DEFAULT_GRAPH_PATH), desc))
