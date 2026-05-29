from pathlib import Path
from agent_a5_baseline_compare import SPEC, run_agent
from common_utils import DEFAULT_GRAPH_PATH, TOOL_PURPOSE
from tests.test_helper import run_agent_case

if __name__ == "__main__":
    desc = "\n".join([f"{name}:{TOOL_PURPOSE.get(name,'')}" for name in SPEC.tool_names])
    prompt = (
        "陈女士老人因BPSD症状加重住院治疗后，症状缓解并治愈出院，准备返回照护机构，"
        "目前老人精神状态平稳，BPSD症状较住院前明显改善，现提供其住院前ECR摘要及出院摘要结构化包作为核心输入：\n\n"
        "住院前ECR摘要核心信息：老人确诊阿尔茨海默病性痴呆4年余，长期存在BPSD症状，近期症状加重，"
        "表现为拒绝进食、拒绝配合康复训练、不愿与人交流且情绪躁动，NPI评分22分；"
        "有心脏起搏器植入、胆囊切除术后史，血压、血脂控制不佳，未规律服药；"
        "日常生活能力方面，可独立进食、穿衣，平地行走需部分辅助，洗澡需他人协助；"
        "家属因长期照护老人且近期症状加重，存在明显照护焦虑，缺乏专业照护知识；"
        "此次因BPSD症状加重急诊入院，入院时情绪躁动，生命体征基本平稳。\n\n"
        "出院摘要结构化包核心信息：老人BPSD症状明显缓解，NPI评分降至16分，情绪趋于平稳，可配合基础照护；"
        "生命体征平稳，心率维持在60次/分，睡眠、饮食规律；"
        "医嘱要求规律服用降压、调脂药物，每日监测血压；"
        "日常生活能力无明显变化，仍需部分辅助平地行走；"
        "照护重点明确为跌倒防护、规律服药、认知非药物干预、BPSD症状监测及家属支持。\n\n"
        "请智能体精准提取两组文档中的核心健康数据、功能状态、照护重点等信息，"
        "多维度对比老人住院前后的健康变化，清晰识别状态变化趋势，"
        "生成详细、客观的ECR状态对比报告，为后续返院照护方案制定提供数据支撑。"
    )
    print(run_agent_case("a5_baseline_compare", run_agent, prompt, Path(DEFAULT_GRAPH_PATH), desc))
