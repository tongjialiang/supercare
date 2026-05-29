from pathlib import Path
from agent_a6_task_pack_agent import SPEC, run_agent
from common_utils import DEFAULT_GRAPH_PATH, TOOL_PURPOSE
from tests.test_helper import run_agent_case

if __name__ == "__main__":
    desc = "\n".join([f"{name}:{TOOL_PURPOSE.get(name,'')}" for name in SPEC.tool_names])
    prompt = (
        "陈女士老人因BPSD症状加重住院治疗后，症状缓解并顺利返院，目前返院初期，精神状态平稳，"
        "BPSD症状较住院前明显改善（NPI评分16分），但仍有潜在复发风险，现提供其ECR状态对比报告作为核心输入：\n\n"
        "报告核心内容：老人住院前有阿尔茨海默病性痴呆、心脏起搏器植入、胆囊切除术后等基础疾病，"
        "血压血脂控制不佳，因BPSD症状加重（NPI评分22分）入院；出院后BPSD症状明显缓解，NPI评分降至16分，"
        "情绪平稳，可配合基础照护；生命体征平稳（心率60次/分），睡眠规律；"
        "医嘱要求规律服用降压、调脂药物，每日监测血压；"
        "日常生活能力方面，可独立完成进食、穿衣、如厕，平地行走需部分辅助，洗澡需全程协助；"
        "仍存在轻微BPSD相关表现，偶有拒绝配合简单活动的情况，日常喜好跳舞；"
        "家属有长期照护焦虑，尤其担心老人BPSD症状复发，缺乏专业照护指导；"
        "照护核心重点为规律服药、跌倒防护、认知非药物干预、BPSD症状监测及家属支持。\n\n"
        "请智能体精准解读对比报告，结合老人返院后的适应需求、健康风险、BPSD症状恢复情况及跳舞喜好，"
        "拆分出可落地、可执行的专项照护任务，明确各任务的执行标准、频次及注意事项，"
        "生成规范的返院适应期专项任务包，重点涵盖用药指导、跌倒防护、认知干预（结合跳舞喜好）、"
        "BPSD症状监测、家属支持五大模块，确保照护团队能按任务包有序开展照护工作，预防BPSD症状复发。"
    )
    print(run_agent_case("a6_task_pack", run_agent, prompt, Path(DEFAULT_GRAPH_PATH), desc))
