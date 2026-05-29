from pathlib import Path
from agent_a10_trend_comparison_agent import SPEC, run_agent
from common_utils import DEFAULT_GRAPH_PATH, TOOL_PURPOSE
from tests.test_helper import run_agent_case

if __name__ == "__main__":
    desc = "\n".join([f"{name}:{TOOL_PURPOSE.get(name,'')}" for name in SPEC.tool_names])
    prompt = (
        "陈女士老人返院第5天，整体状态平稳，BPSD症状持续缓解，无复发情况，"
        "为清晰掌握老人健康变化趋势，现提供其住院前、出院时、返院D5三个关键时间点的核心健康数据：\n\n"
        "1. 住院前：血压145/90mmHg，总胆固醇6.8mmol/L（血脂偏高），NPI评分22分"
        "（重度精神行为异常，BPSD症状明显，表现为拒绝进食、情绪躁动），ADL评分65分"
        "（轻度功能障碍，平地行走辅助需求较高），家属焦虑明显，未规律服药；\n"
        "2. 出院时：血压135/85mmHg，总胆固醇6.5mmol/L（血脂较前下降），NPI评分16分"
        "（BPSD症状缓解，情绪平稳），ADL评分65分（功能状态无明显变化），"
        "生命体征平稳（心率60次/分），医嘱要求规律服药，照护重点明确为BPSD症状监测、认知干预等；\n"
        "3. 返院D5：血压130/80mmHg（血脂控制可），总胆固醇6.2mmol/L，NPI评分15分"
        "（BPSD症状持续缓解，偶有拒绝配合康复，无过激行为），ADL评分70分"
        "（功能状态略有改善，平地行走辅助需求减少），生命体征平稳，规律服药无异常，睡眠规律，"
        "已发生1起轻微BPSD事件（经干预后未复发），家属焦虑略有缓解，照护措施有序落实，无BPSD症状复发加重情况。\n\n"
        "请智能体精准提取上述三时点的核心健康数据，通过图表形式直观呈现各数据的变化趋势，"
        "同时配套详细说明，清晰解读数据波动规律及老人健康状态的好转趋势，"
        "重点突出BPSD症状的恢复情况，为后续照护方案调整、BPSD复发预防、风险预判提供可视化支撑。"
    )
    print(run_agent_case("a10_trend_comparison", run_agent, prompt, Path(DEFAULT_GRAPH_PATH), desc))
