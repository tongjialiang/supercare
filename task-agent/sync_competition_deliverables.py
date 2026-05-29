#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 A0/A3/A15 等交付物同步至比赛文档/交付物 目录。"""

from __future__ import annotations

import shutil
from pathlib import Path

TASK_OUTPUT = Path("/srv/supercare/task-agent/output")
COMPETITION = Path("/srv/supercare/比赛文档")
DELIVERABLE = COMPETITION / "交付物"

# (源 glob 或文件名, 目标子目录说明)
COPY_FILES = [
    "a0_老年健康生物标志物矩阵.xlsx",
    "a0_序贯疾病分期结果.json",
    "a0_SuStaIn_MCMC分期结果.json",
    "a0_贝叶斯风险后验.json",
    "a0_计算方法与核心思想.md",
    "a0_疾病进展曲线_陈女士.png",
    "a0_生物标志物分期进展热图_陈女士.png",
    "a0_序贯事件进展图_陈女士.png",
    "a0_贝叶斯先验后验图_陈女士.png",
    "本地序贯分期与贝叶斯风险融合_算法说明.docx",
    "2_PPT_超级[GP-护士-照护员]智能体协同算法_含序贯贝叶斯_20260525.pptx",
    "1_技术报告_超级[GP-护士-照护员]智能体协同算法_含序贯贝叶斯_20260525.docx",
    "a0_先验文献依据.md",
    "a3_GP协作专业答复.pdf",
    "a3_GP协作专业答复.md",
    "a15_老年健康序贯分期与贝叶斯风险报告.pdf",
    "a15_老年健康序贯分期与贝叶斯风险报告.md",
    "整体叙事图_本地序贯分期与超级GP协同.md",
    "整体叙事图_本地序贯分期与超级GP协同.png",
    "整体叙事图_本地序贯分期与超级GP协同.jpg",
]

DOC_COPIES = [
    (COMPETITION / "6_创新点_SuStaIn分期与贝叶斯风险融合.md", "6_创新点_本地序贯分期与贝叶斯风险融合.md"),
]


def main() -> None:
    DELIVERABLE.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in COPY_FILES:
        src = TASK_OUTPUT / name
        if not src.is_file() and (COMPETITION / name).is_file():
            src = COMPETITION / name
        if src.is_file():
            shutil.copy2(src, DELIVERABLE / name)
            copied.append(name)
        else:
            print(f"跳过（不存在）: {name}")

    innov_src = Path("/srv/supercare/比赛文档/6_创新点_本地序贯分期与贝叶斯风险融合.md")
    if not innov_src.is_file():
        old = COMPETITION / "6_创新点_SuStaIn分期与贝叶斯风险融合.md"
        if old.is_file():
            text = old.read_text(encoding="utf-8")
            text = text.replace("SuStaIn", "本地序贯疾病分期").replace("pySuStaIn", "本地算法模块")
            text = text.replace("Young et al.", "").replace("SuStaIn-inspired", "本地实现")
            innov_src.write_text(text, encoding="utf-8")

    if innov_src.is_file():
        shutil.copy2(innov_src, DELIVERABLE / innov_src.name)
        copied.append(innov_src.name)

    narrative_src = COMPETITION / "7_整体叙事图_本地序贯分期与超级GP协同.md"
    if narrative_src.is_file():
        shutil.copy2(narrative_src, DELIVERABLE / narrative_src.name)
        copied.append(narrative_src.name)

    readme = DELIVERABLE / "README_交付物清单.txt"
    readme.write_text(
        "比赛交付物目录（自动生成）\n\n" + "\n".join(f"- {n}" for n in copied) + "\n",
        encoding="utf-8",
    )
    print(f"已同步 {len(copied)} 个文件到 {DELIVERABLE}")


if __name__ == "__main__":
    main()
