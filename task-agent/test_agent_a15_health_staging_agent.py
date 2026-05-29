#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A15 分期智能体测试。"""

from agent_a15_health_staging_agent import run_agent

prompt = """
请为陈女士老人生成《老年健康序贯分期与贝叶斯风险报告》。
背景：68岁，阿尔茨海默病性痴呆，BPSD 返院适应期，需超级 GP 制定针对性照护方案。
必须引用 tool_疾病分期洞察 与 tool_贝叶斯风险后验 中的数值；使用「本地序贯疾病分期模型」表述，勿写外部产品名。
""".strip()

if __name__ == "__main__":
    print("=== 运行 A15 (use_tools=True) ===", flush=True)
    result = run_agent(prompt, use_tools=True)
    print("success:", result.get("success"))
    print("pdf:", result.get("pdf_path"))
    print("md:", result.get("md_path"))
