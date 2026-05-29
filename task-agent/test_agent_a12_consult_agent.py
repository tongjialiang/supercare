from pathlib import Path
from agent_a12_consult_agent import SPEC, run_agent
from common_utils import DEFAULT_GRAPH_PATH, TOOL_PURPOSE
from tests.test_helper import run_agent_case

if __name__ == "__main__":
    desc = "\n".join([f"{name}:{TOOL_PURPOSE.get(name,'')}" for name in SPEC.tool_names])
    prompt = (
        "陈女士老人返院一周后，整体状态平稳，BPSD症状持续缓解，但近2天出现新的健康异常情况，"
        "为进一步优化照护方案、预防BPSD症状复发，安排精神科远程会诊，"
        "现提供《返院一周综合报告》及老人新发生的健康状况描述作为核心输入：\n\n"
        "《返院一周综合报告》核心内容：老人返院一周内仅发生1次轻微BPSD事件，干预后未复发，"
        "BPSD症状持续缓解（NPI评分15分）；血压血脂控制良好，生命体征平稳；"
        "照护团队结合其跳舞喜好调整干预方式，家属焦虑略有缓解；"
        "照护亮点为跌倒防护到位、用药规范、BPSD事件干预有效，"
        "不足为康复配合度及家属对BPSD复发的焦虑需进一步加强。\n\n"
        "新发生的健康状况描述：近2天（返院第6、7天），照护员在照护过程中发现，"
        "老人在活动区自主练习跳舞时，偶尔会出现短暂记忆空白，具体表现为突然忘记正在跳的舞步，"
        "停顿发呆，持续约1-2分钟后恢复正常，恢复后无明显不适，但情绪会略显低落，"
        "拒绝与其他老人一起跳舞、交流；家属探视时发现该情况后，担心老人认知功能进一步下降，"
        "且担心此症状会诱发BPSD症状复发，原本缓解的焦虑情绪有所反复，"
        "多次向照护团队询问老人认知状态及BPSD复发风险，请求进一步干预。\n\n"
        "请智能体精准整合一周综合报告及新健康状况信息，规范撰写精神科远程会诊记录，"
        "明确会诊目的、会诊参与人员、诊疗意见及后续照护、家属支持方案，"
        "确保会诊信息完整、逻辑清晰，持续缓解BPSD症状、预防复发。"
    )
    print(run_agent_case("a12_consult", run_agent, prompt, Path(DEFAULT_GRAPH_PATH), desc))
