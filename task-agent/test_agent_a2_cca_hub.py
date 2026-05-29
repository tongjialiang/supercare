from pathlib import Path
from agent_a2_cca_hub import SPEC, run_agent
from common_utils import DEFAULT_GRAPH_PATH, TOOL_PURPOSE
from tests.test_helper import run_agent_case

if __name__ == "__main__":
    desc = "\n".join([f"{name}:{TOOL_PURPOSE.get(name,'')}" for name in SPEC.tool_names])
    prompt = (
        "上海籍失智老人陈女士返院第5天，老人小学学历、丧偶，育有1名子女，无宗教信仰，日常喜好跳舞。"
        "已知其有阿尔茨海默病性痴呆、心脏起搏器植入、胆囊切除术后史，2025年11月头部外伤后遗留右额部皮下血肿，"
        "2024年体检提示血压偏高、血脂异常、心电图T波变化；BPSD症状表现为拒绝配合康复及集体活动，"
        "生命体征平稳（心率长期60次/分），睡眠规律，平地行走需部分辅助。"
        "提供老人住院前、出院时、D5的血压、血脂相关数据及照护记录，"
        "测试智能体是否能出具准确评估结论，制定针对性周护理任务（重点涵盖跌倒防护、规律服药、认知干预），并规范指导D5数据录入。"
    )
    print(run_agent_case("a2_cca_hub", run_agent, prompt, Path(DEFAULT_GRAPH_PATH), desc))
