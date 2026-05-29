from pathlib import Path
from agent_a8_escalation_decision_agent import SPEC, run_agent
from common_utils import DEFAULT_GRAPH_PATH, TOOL_PURPOSE
from tests.test_helper import run_agent_case

if __name__ == "__main__":
    desc = "\n".join([f"{name}:{TOOL_PURPOSE.get(name,'')}" for name in SPEC.tool_names])
    prompt = (
        "陈女士老人返院第3天发生一起轻微BPSD相关事件（拒绝配合康复训练，无过激行为），"
        "目前老人情绪已趋于平稳，生命体征正常，BPSD症状未出现复发加重的情况，"
        "现提供完整的《BPSD事件报告》作为核心输入：\n\n"
        "报告核心内容：事件发生于返院第3天上午10点，地点为机构活动区；老人68岁，上海籍，"
        "有阿尔茨海默病性痴呆、心脏起搏器植入、胆囊切除术后史，近期因BPSD症状加重住院治疗，缓解后返院，"
        "目前BPSD症状较住院前明显改善（NPI评分16分），日常喜好跳舞，"
        "返院后照护重点为规律服药、跌倒防护、认知干预、BPSD症状监测及家属支持；"
        "事件核心为老人拒绝配合结合跳舞喜好设计的简易康复训练，表现为沉默、拒绝沟通，无过激行为，"
        "较住院时的躁动症状明显好转，照护员采取针对性安抚措施后，老人情绪缓解但仍不配合康复；"
        "老人子女探视时目睹该场景，担心BPSD症状复发，焦虑情绪明显，咨询干预方法；"
        "事件发生期间，老人生命体征平稳，心率维持在60次/分，无头晕、头痛、胸闷等不适，"
        "日常规律服用降压、调脂药物，血压血脂控制平稳，无跌倒、走失、突发疾病等异常情况，整体状态平稳。\n\n"
        "请智能体准确判断该BPSD事件的严重程度，结合老人的基础疾病、BPSD症状恢复情况、生命体征及家属状态，"
        "分析事件的发展趋势及潜在风险，给出科学合理的处置建议，"
        "明确判断是否需要启动升级流程（如护士介入、GP介入），规避照护风险，预防BPSD症状复发。"
    )
    print(run_agent_case("a8_escalation_decision", run_agent, prompt, Path(DEFAULT_GRAPH_PATH), desc))
