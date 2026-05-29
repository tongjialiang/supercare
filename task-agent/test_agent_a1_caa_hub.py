from pathlib import Path
from agent_a1_caa_hub import SPEC, run_agent
from common_utils import DEFAULT_GRAPH_PATH, TOOL_PURPOSE
from tests.test_helper import run_agent_case

if __name__ == "__main__":
    desc = "\n".join([f"{name}:{TOOL_PURPOSE.get(name,'')}" for name in SPEC.tool_names])
    prompt = (
        "陈女士，上海籍失智老人，有阿尔茨海默病性痴呆病史，曾植入心脏起搏器、行胆囊切除术，近期因头部外伤急诊（右额部皮下血肿）返院照护。"
        "照护员反馈，老人日常喜好跳舞，但存在BPSD症状，拒绝配合康复训练，家属照护关注度高且有长期照护焦虑，照护中需重点防护跌倒、指导规律服药，同时需对其认知相关行为进行非药物干预。"
        "测试智能体是否能结合老人情况，指导照护员制定贴合其喜好的干预方式，缓解家属焦虑，规范落实照护重点并反馈执行要点。"
    )
    print(run_agent_case("a1_caa_hub", run_agent, prompt, Path(DEFAULT_GRAPH_PATH), desc))
