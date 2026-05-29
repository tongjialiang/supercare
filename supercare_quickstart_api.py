#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SuperCare 快速运行 API：一键触发四大模块流水线。

启动：
  pip install -r requirements-data-agent1.txt -r requirements-quickstart.txt
启动：
  bash scripts/install_quickstart_api_service.sh   # 常驻 + 开机自启
  # 或 bash scripts/start_quickstart_api.sh        # nohup 后台

文档：http://127.0.0.1:8765/docs
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Path as ApiPath, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

PROJECT_ROOT = Path("/srv/supercare")
TASK_AGENT_ROOT = PROJECT_ROOT / "task-agent"
JOB_DIR = PROJECT_ROOT / ".quickstart_jobs"
JOB_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_EXCEL = PROJECT_ROOT / "DataSource/陈女士/ms_chen_CareCase.xlsx"
DEFAULT_GRAPH = (
    PROJECT_ROOT
    / "data-agent1/ms_chen_CareCase/results/ms_chen_CareCase_elder_health_computing_graph.json"
)
DEFAULT_CONFIG = PROJECT_ROOT / "config/data_agent1_config.json"

DATA_AGENT1_RESULTS = PROJECT_ROOT / "data-agent1/ms_chen_CareCase/results"
DATA_AGENT2_CORPUS_DIR = PROJECT_ROOT / "data-agent2/ms_chen_CareCase/training_corpus"
TASK_AGENT_OUTPUT = TASK_AGENT_ROOT / "output"

# 四大模块统一中文名称
MODULE_DATA_AGENT1 = "长者智能计算图 DataAgent"
MODULE_DATA_AGENT2 = "三超循证知识基座 DataAgent"
MODULE_STAGING_BAYESIAN = "序贯分期与贝叶斯风险融合推断算法"
MODULE_TASK_AGENT = "超级「GP-护士-照护员」智能体协同算法"

# 语料文件名 → 说明（DataAgent2 training_corpus）
CORPUS_FILE_DESCRIPTIONS: Dict[str, str] = {
    "super_doctor_with_cot_50.jsonl": "超级医生带思维链语料 50 条，含 L1–L4 四层循证轨迹与证据引用，供 GP 决策微调。",
    "super_doctor_without_cot_50.jsonl": "超级医生无思维链语料 50 条，仅保留问答对，用于对比 CoT 增益的消融实验。",
    "super_nurse_with_cot_50.jsonl": "超级护士带思维链语料 50 条，覆盖评估结论、护理调整与风险预警等场景。",
    "super_nurse_without_cot_50.jsonl": "超级护士无思维链语料 50 条，结构与医生语料对称，便于跨角色质量对比。",
    "super_caregiver_with_cot_50.jsonl": "超级照护员带思维链语料 50 条，聚焦日常照护动作、非药物干预与家属沟通。",
    "super_caregiver_without_cot_50.jsonl": "超级照护员无思维链语料 50 条，用于验证四层注入对实操建议质量的影响。",
}

# TaskAgent A1–A15 PDF 文件名 → 说明
TASK_AGENT_PDF_DESCRIPTIONS: Dict[str, str] = {
    "a1_照护员协作专业答复.pdf": "超级照护员（CAA Hub）输出的非药物干预与日常执行方案，含跳舞兴趣引导、防跌倒要点。",
    "a2_护士协作专业答复.pdf": "超级护士（CCA Hub）输出的临床评估与护理调整建议，衔接医生决策与一线执行。",
    "a3_GP协作专业答复.pdf": "超级 GP（CDA Hub）综合确认意见，统筹多角色协同照护路径与风险管控。",
    "a4_出院摘要结构化包.pdf": "Discharge Parser 将出院病历解析为结构化字段包，供后续智能体统一读取。",
    "a5_ECR状态对比报告.pdf": "入院、出院、返院三时点的 ECR（情绪-认知-行为）状态横向对比分析。",
    "a6_返院适应期专项任务包.pdf": "返院适应期任务拆解清单，明确照护员、护士在各日的可执行动作。",
    "a7_BPSD事件报告.pdf": "BPSD 行为事件的时序记录与情境描述，为升级决策提供结构化输入。",
    "a8_BPSD事件处理建议.pdf": "Escalation Agent 针对 BPSD 事件的即时处置方案与是否升级会诊的建议。",
    "a9_照护员周重点任务.pdf": "照护员本周重点任务与操作步骤，源自护士评估结论的下钻执行版。",
    "a9_护士评估结论与调整建议.pdf": "护士周评估结论、生命体征与 ADL 变化摘要及护理计划调整建议。",
    "a10_三时点功能对比图.pdf": "住院前、出院、返院三个时间节点的 ADL/NPI 等功能指标可视化对比。",
    "a11_返院一周综合报告.pdf": "返院第 7 天综合状态复盘，汇总行为、功能、体征与家属反馈。",
    "a12_精神科远程会诊记录.pdf": "精神科远程会诊意见，含 BPSD 前驱信号识别与非药物干预优化建议。",
    "a13_D30再稳定评估报告.pdf": "返院第 30 天再稳定期评估，判断 BPSD 是否进入低复发风险稳定期。",
    "a13_照护成效中期报告.pdf": "返院 30 天照护成效中期总结，量化 NPI/ADL 改善与不良事件控制情况。",
    "a14_TaskAgent审计评估报告.pdf": "A1–A14 全链路执行审计报告，记录各智能体调用顺序、产出与质量评分。",
    "a15_老年健康序贯分期与贝叶斯风险报告.pdf": "A0 序贯分期与贝叶斯风险融合的综合算法报告，含文献先验与后验解读。",
}

_jobs_lock = threading.Lock()
_jobs: Dict[str, Dict[str, Any]] = {}


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class PipelineRunRequest(BaseModel):
    """一键全链路运行参数（默认值为答辩演示推荐配置）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "fast_mode": True,
                    "skip_task_agent": False,
                    "demo_task_agent": True,
                }
            ]
        }
    )

    fast_mode: bool = Field(
        default=True,
        description=(
            "长者智能计算图 DataAgent 解析模式。"
            "true=openpyxl 加速（约 1–2 分钟，答辩演示推荐）；"
            "false=MinerU 正式模式（需配置 mineru.api_url，质量更高、耗时更长）。"
        ),
        examples=[True],
    )
    skip_task_agent: bool = Field(
        default=False,
        description=(
            "是否跳过第四模块。"
            "false=跑完整四大模块（推荐）；"
            "true=仅运行 DataAgent1 → DataAgent2 → 序贯贝叶斯，不启动协同智能体。"
        ),
        examples=[False],
    )
    demo_task_agent: bool = Field(
        default=True,
        description=(
            "协同智能体运行范围。"
            "true=仅演示 A3 超级 GP（约 1–3 分钟，答辩演示推荐）；"
            "false=全量运行 A1–A14（耗时较长，产出完整 PDF 与照护科学实践图谱）。"
        ),
        examples=[True],
    )


class StepRunRequest(BaseModel):
    """单模块运行参数（默认 openpyxl 演示模式）。"""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"parser_mode": "openpyxl"},
            ]
        }
    )

    parser_mode: str = Field(
        default="openpyxl",
        description=(
            "长者智能计算图 DataAgent 文档解析模式。"
            "openpyxl=快速演示（默认）；"
            "mineru=正式 MinerU 解析（需 mineru.api_url）。"
        ),
        examples=["openpyxl"],
    )


OPENAPI_TAGS = [
    {
        "name": "概览",
        "description": "服务入口与四大模块说明。",
    },
    {
        "name": "配置与状态",
        "description": "检查 API 服务状态、配置文件与示例数据是否就绪。",
    },
    {
        "name": "产物查看",
        "description": "查看流水线关键产物是否生成，获取下载链接并下载文件。",
    },
    {
        "name": "任务查询",
        "description": "查询后台任务执行进度与日志摘要。全链路运行后请轮询 job_id 直至 status=success。",
    },
    {
        "name": "模块运行",
        "description": "单独启动某一模块，适合分步调试或局部复现。",
    },
    {
        "name": "全链路运行",
        "description": "一键顺序执行四大模块，推荐答辩演示入口。",
    },
]

API_DESCRIPTION = """
## SuperCare 快速运行 API

四大模块流水线：

1. **长者智能计算图 DataAgent** — 解析 CareCase Excel，生成长者健康计算图
2. **三超循证知识基座 DataAgent** — 基于计算图生成六份 JSONL 训练语料
3. **序贯分期与贝叶斯风险融合推断算法** — A0 本地序贯分期 + 贝叶斯后验 + 配图
4. **超级「GP-护士-照护员」智能体协同算法** — A1–A15 协同产出 PDF / 语料 / 实践图谱

### 推荐演示流程

1. `POST /run/pipeline/all` — 使用默认参数直接 Execute
2. `GET /jobs/{job_id}` — 轮询任务状态直至 success
3. `GET /outputs/links` — 获取全部产物下载链接
4. `GET /outputs/download?key=...` — 下载指定文件

详细说明见：`比赛文档/快速运行指南.md`
"""

# Swagger 演示用默认 download key
DEMO_DOWNLOAD_KEY = "taskagent_a3_GP协作专业答复"
DEMO_DOWNLOAD_KEY_ALT = "care_science_practice_graph_jpg"


app = FastAPI(
    title="SuperCare 快速运行 API",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,
)


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _save_job(job: Dict[str, Any]) -> None:
    job_path = JOB_DIR / f"{job['job_id']}.json"
    job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    with _jobs_lock:
        _jobs[job["job_id"]] = job


def _load_jobs() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for job_file in sorted(JOB_DIR.glob("*.json"), reverse=True):
        try:
            rows.append(json.loads(job_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return rows


def _create_job(step_name: str, command: List[str]) -> Dict[str, Any]:
    job = {
        "job_id": uuid.uuid4().hex[:12],
        "step": step_name,
        "status": JobStatus.pending.value,
        "command": " ".join(command),
        "started_at": _now_text(),
        "finished_at": "",
        "duration_seconds": 0.0,
        "stdout_tail": "",
        "stderr_tail": "",
        "output_paths": [],
        "error": "",
    }
    _save_job(job)
    return job


def _run_subprocess(job_id: str, command: List[str], cwd: Path) -> None:
    with _jobs_lock:
        job = dict(_jobs[job_id])
    job["status"] = JobStatus.running.value
    _save_job(job)

    begin_time = datetime.now()
    try:
        process = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=7200,
        )
        job["stdout_tail"] = (process.stdout or "")[-4000:]
        job["stderr_tail"] = (process.stderr or "")[-2000:]
        job["duration_seconds"] = round((datetime.now() - begin_time).total_seconds(), 2)
        job["finished_at"] = _now_text()
        if process.returncode == 0:
            job["status"] = JobStatus.success.value
        else:
            job["status"] = JobStatus.failed.value
            job["error"] = f"退出码 {process.returncode}"
    except subprocess.TimeoutExpired:
        job["status"] = JobStatus.failed.value
        job["error"] = "执行超时（>7200s）"
        job["finished_at"] = _now_text()
    except Exception as exc:
        job["status"] = JobStatus.failed.value
        job["error"] = str(exc)
        job["finished_at"] = _now_text()
    _save_job(job)


def _start_job(step_name: str, command: List[str], cwd: Path) -> Dict[str, Any]:
    job = _create_job(step_name, command)
    thread = threading.Thread(target=_run_subprocess, args=(job["job_id"], command, cwd), daemon=True)
    thread.start()
    return job


def _check_config() -> Dict[str, Any]:
    issues: List[str] = []
    if not DEFAULT_CONFIG.is_file():
        issues.append(f"缺少配置文件：{DEFAULT_CONFIG}")
    else:
        try:
            config_payload = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
            qwen_key = (config_payload.get("qwen") or {}).get("api_key", "").strip()
            if not qwen_key:
                issues.append("config/data_agent1_config.json 中 qwen.api_key 未填写")
        except json.JSONDecodeError:
            issues.append("配置文件 JSON 格式错误")
    if not DEFAULT_EXCEL.is_file():
        issues.append(f"缺少示例 Excel：{DEFAULT_EXCEL}")
    return {"ready": len(issues) == 0, "issues": issues}


def _collect_key_outputs() -> Dict[str, List[str]]:
    candidates = [
        DEFAULT_GRAPH,
        PROJECT_ROOT / "data-agent2/batch_summary.json",
        TASK_AGENT_ROOT / "output/a0_序贯疾病分期结果.json",
        TASK_AGENT_ROOT / "output/a0_贝叶斯风险后验.json",
        TASK_AGENT_ROOT / "output/a3_GP协作专业答复.pdf",
        TASK_AGENT_ROOT / "output/a15_老年健康序贯分期与贝叶斯风险报告.pdf",
    ]
    return {
        "existing_outputs": [str(path) for path in candidates if path.is_file()],
        "missing_outputs": [str(path) for path in candidates if not path.is_file()],
    }


def _build_output_download_catalog() -> List[Dict[str, Any]]:
    """构建完整输出产物目录（含路径与内容说明）。"""
    catalog: List[Dict[str, Any]] = [
        {
            "key": "data_agent1_graph_json",
            "label": "健康计算图 JSON",
            "module": MODULE_DATA_AGENT1,
            "path": DATA_AGENT1_RESULTS / "ms_chen_CareCase_elder_health_computing_graph.json",
            "description": "陈女士病例的长者健康计算图结构化数据，含节点、边、洞察与证据链，供下游模块读取。",
        },
        {
            "key": "data_agent1_graph_png",
            "label": "健康计算图 PNG",
            "module": MODULE_DATA_AGENT1,
            "path": DATA_AGENT1_RESULTS / "ms_chen_CareCase_elder_health_computing_graph.png",
            "description": "健康计算图可视化展示图，用于答辩演示节点类别、关联关系与关键洞察分布。",
        },
        {
            "key": "data_agent2_batch_summary",
            "label": "batch_summary.json",
            "module": MODULE_DATA_AGENT2,
            "path": PROJECT_ROOT / "data-agent2/batch_summary.json",
            "description": "六份训练语料的批量生成汇总，含各角色 CoT/非 CoT 语料的条数、质量指标与对比结论。",
        },
        {
            "key": "a0_staging_event_png",
            "label": "a0_序贯事件进展图_陈女士.png",
            "module": MODULE_STAGING_BAYESIAN,
            "path": TASK_AGENT_OUTPUT / "a0_序贯事件进展图_陈女士.png",
            "description": "SuStaIn/MCMC 序贯事件槽位与共同分期进展示意图，展示各生物标志物事件在时间轴上的排列。",
        },
        {
            "key": "a0_biomarker_heatmap_png",
            "label": "a0_生物标志物分期进展热图_陈女士.png",
            "module": MODULE_STAGING_BAYESIAN,
            "path": TASK_AGENT_OUTPUT / "a0_生物标志物分期进展热图_陈女士.png",
            "description": "多生物标志物纵向序贯进展热图，直观对比各指标在不同分期的异常程度变化。",
        },
        {
            "key": "a0_disease_curve_png",
            "label": "a0_疾病进展曲线_陈女士.png",
            "module": MODULE_STAGING_BAYESIAN,
            "path": TASK_AGENT_OUTPUT / "a0_疾病进展曲线_陈女士.png",
            "description": "以共同分期为横轴、归一化进展指数为纵轴的疾病进展曲线，呈现多标志物协同演变趋势。",
        },
        {
            "key": "a0_bayesian_prior_posterior_png",
            "label": "a0_贝叶斯先验后验图_陈女士.png",
            "module": MODULE_STAGING_BAYESIAN,
            "path": TASK_AGENT_OUTPUT / "a0_贝叶斯先验后验图_陈女士.png",
            "description": "文献校准贝叶斯先验与观测似然更新后的后验对比图，展示各分期风险概率变化。",
        },
        {
            "key": "a13_d30_corpus_jsonl",
            "label": "a13_D30高价值语料.jsonl",
            "module": MODULE_TASK_AGENT,
            "path": TASK_AGENT_OUTPUT / "a13_D30高价值语料.jsonl",
            "description": "Outcome Report Agent 从 D30 照护闭环中提炼的高价值问答语料，用于后续模型微调与成效复盘。",
        },
        {
            "key": "care_science_practice_graph_jpg",
            "label": "照护科学实践图谱.jpg",
            "module": MODULE_TASK_AGENT,
            "path": TASK_AGENT_OUTPUT / "照护科学实践图谱.jpg",
            "description": "从 A1–A14 实践 PDF 凝练的照护科学实践图谱可视化，以超级照护员、护士、GP 为三认知核心向外辐射。",
        },
    ]

    if DATA_AGENT2_CORPUS_DIR.is_dir():
        for corpus_file in sorted(DATA_AGENT2_CORPUS_DIR.glob("*.jsonl")):
            catalog.append(
                {
                    "key": f"da2_corpus_{corpus_file.stem}",
                    "label": corpus_file.name,
                    "module": MODULE_DATA_AGENT2,
                    "path": corpus_file,
                    "description": CORPUS_FILE_DESCRIPTIONS.get(
                        corpus_file.name,
                        f"DataAgent2 生成的训练语料：{corpus_file.name}。",
                    ),
                }
            )

    for pdf_file in sorted(TASK_AGENT_OUTPUT.glob("a*.pdf")):
        pdf_name = pdf_file.name
        agent_prefix = pdf_name.split("_", 1)[0]
        if not agent_prefix[1:].isdigit():
            continue
        agent_number = int(agent_prefix[1:])
        if agent_number < 1 or agent_number > 15:
            continue
        catalog.append(
            {
                "key": f"taskagent_{pdf_file.stem}",
                "label": pdf_name,
                "module": MODULE_TASK_AGENT,
                "path": pdf_file,
                "description": TASK_AGENT_PDF_DESCRIPTIONS.get(
                    pdf_name,
                    f"协同智能体产出 PDF：{pdf_name}。",
                ),
            }
        )

    return catalog


def _get_output_key_map() -> Dict[str, Path]:
    return {item["key"]: item["path"] for item in _build_output_download_catalog()}


def _resolve_download_file(output_key: str) -> Path:
    """根据 key 解析可下载的输出文件。"""
    output_key_map = _get_output_key_map()
    if output_key not in output_key_map:
        raise HTTPException(
            status_code=400,
            detail=f"未知 key：{output_key}，可用值见 GET /outputs/links",
        )
    file_path = output_key_map[output_key]
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"文件尚未生成：{file_path}")
    return file_path


def _build_output_download_links(base_url: str) -> List[Dict[str, Any]]:
    """构建全部产物的下载链接列表。"""
    base_url = base_url.rstrip("/")
    download_links: List[Dict[str, Any]] = []
    for catalog_item in _build_output_download_catalog():
        file_path = catalog_item["path"]
        file_exists = file_path.is_file()
        download_links.append(
            {
                "key": catalog_item["key"],
                "label": catalog_item["label"],
                "module": catalog_item["module"],
                "description": catalog_item["description"],
                "path": str(file_path),
                "exists": file_exists,
                "size_bytes": file_path.stat().st_size if file_exists else 0,
                "download_url": f"{base_url}/outputs/download?key={catalog_item['key']}"
                if file_exists
                else None,
            }
        )
    return download_links


def _command_data_agent1(parser_mode: str) -> List[str]:
    return [
        sys.executable,
        str(PROJECT_ROOT / "data_agent_task1.py"),
        "--input",
        str(DEFAULT_EXCEL),
        "--output-root",
        str(PROJECT_ROOT / "data-agent1"),
        "--config",
        str(DEFAULT_CONFIG),
        "--parser-mode",
        parser_mode,
    ]


def _command_data_agent2() -> List[str]:
    graph_path = DEFAULT_GRAPH if DEFAULT_GRAPH.is_file() else (
        PROJECT_ROOT
        / "data-agent1/ms_chen_CareCase/results/ms_chen_CareCase_elder_health_computing_graph.json"
    )
    return [
        sys.executable,
        str(PROJECT_ROOT / "data_agent_task2.py"),
        "--input-graph",
        str(graph_path),
        "--output-root",
        str(PROJECT_ROOT / "data-agent2"),
        "--config",
        str(DEFAULT_CONFIG),
    ]


def _command_staging() -> List[str]:
    return [sys.executable, str(TASK_AGENT_ROOT / "run_staging_pipeline.py")]


def _command_staging_viz() -> List[str]:
    return [sys.executable, str(TASK_AGENT_ROOT / "generate_a0_visualizations.py")]


def _command_task_agent_demo() -> List[str]:
    return [
        sys.executable,
        str(TASK_AGENT_ROOT / "test_agent_a3_cda_hub.py"),
    ]


def _command_task_agent_full() -> List[str]:
    return [sys.executable, str(TASK_AGENT_ROOT / "run_agents_a1_a14.py")]


def _run_pipeline_background(job_id: str, request: PipelineRunRequest) -> None:
    parser_mode = "openpyxl" if request.fast_mode else "mineru"
    steps = [
        ("data_agent1", _command_data_agent1(parser_mode), PROJECT_ROOT),
        ("data_agent2", _command_data_agent2(), PROJECT_ROOT),
        ("staging", _command_staging(), TASK_AGENT_ROOT),
        ("staging_viz", _command_staging_viz(), TASK_AGENT_ROOT),
    ]
    if not request.skip_task_agent:
        if request.demo_task_agent:
            steps.append(("task_agent_a3_demo", _command_task_agent_demo(), TASK_AGENT_ROOT))
        else:
            steps.append(("task_agent_full", _command_task_agent_full(), TASK_AGENT_ROOT))

    with _jobs_lock:
        pipeline_job = dict(_jobs[job_id])
    pipeline_job["status"] = JobStatus.running.value
    pipeline_job["sub_steps"] = []
    _save_job(pipeline_job)

    begin_time = datetime.now()
    for step_name, command, cwd in steps:
        step_record = {"step": step_name, "status": JobStatus.running.value, "command": " ".join(command)}
        pipeline_job.setdefault("sub_steps", []).append(step_record)
        _save_job(pipeline_job)

        process = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True, timeout=7200)
        step_record["status"] = JobStatus.success.value if process.returncode == 0 else JobStatus.failed.value
        step_record["stdout_tail"] = (process.stdout or "")[-1500:]
        step_record["stderr_tail"] = (process.stderr or "")[-800:]
        _save_job(pipeline_job)

        if process.returncode != 0:
            pipeline_job["status"] = JobStatus.failed.value
            pipeline_job["error"] = f"步骤 {step_name} 失败，退出码 {process.returncode}"
            pipeline_job["finished_at"] = _now_text()
            pipeline_job["duration_seconds"] = round((datetime.now() - begin_time).total_seconds(), 2)
            pipeline_job["output_paths"] = _collect_key_outputs()["existing_outputs"]
            _save_job(pipeline_job)
            return

    pipeline_job["status"] = JobStatus.success.value
    pipeline_job["finished_at"] = _now_text()
    pipeline_job["duration_seconds"] = round((datetime.now() - begin_time).total_seconds(), 2)
    pipeline_job["output_paths"] = _collect_key_outputs()["existing_outputs"]
    _save_job(pipeline_job)


@app.get(
    "/",
    tags=["概览"],
    summary="服务概览",
    description="返回 API 名称、四大模块列表、推荐入口路径。无需参数，用于快速了解服务结构。",
)
def read_root() -> Dict[str, Any]:
    return {
        "service": "SuperCare 快速运行 API",
        "docs": "/docs",
        "modules": [
            MODULE_DATA_AGENT1,
            MODULE_DATA_AGENT2,
            MODULE_STAGING_BAYESIAN,
            MODULE_TASK_AGENT,
        ],
        "quick_start": "POST /run/pipeline/all  （推荐，fast_mode=true）",
        "download_links": "GET /outputs/links",
    }


@app.get(
    "/health",
    tags=["配置与状态"],
    summary="健康检查",
    description="确认 API 服务已启动并可正常响应。返回 status=ok 与当前服务器时间。",
)
def health_check() -> Dict[str, str]:
    return {"status": "ok", "time": _now_text()}


@app.get(
    "/config/check",
    tags=["配置与状态"],
    summary="检查运行配置",
    description=(
        "检查 config/data_agent1_config.json 中 qwen.api_key 是否已填写，"
        "以及示例 Excel 是否存在。ready=true 表示可启动流水线。"
    ),
)
def config_check() -> Dict[str, Any]:
    return _check_config()


@app.get(
    "/outputs",
    tags=["产物查看"],
    summary="检查关键产物路径",
    description=(
        "返回 6 个核心验收文件的存在情况（existing_outputs / missing_outputs）。"
        "用于快速判断全链路是否跑通，不含下载链接。"
    ),
)
def list_outputs() -> Dict[str, Any]:
    return _collect_key_outputs()


@app.get(
    "/outputs/links",
    tags=["产物查看"],
    summary="获取全部产物下载链接",
    description=(
        "返回 32 个输出文件的 key、中文说明、所属模块与 download_url。"
        "by_module 按四大模块分组；仅 exists=true 的文件提供可下载链接。"
    ),
)
def get_output_download_links(request: Request) -> Dict[str, Any]:
    """返回全部输出文件的下载链接与内容说明（已生成的文件提供可点击 URL）。"""
    download_links = _build_output_download_links(str(request.base_url))
    ready_count = sum(1 for item in download_links if item["exists"])
    modules: Dict[str, List[Dict[str, Any]]] = {}
    for item in download_links:
        modules.setdefault(item["module"], []).append(item)
    return {
        "files": download_links,
        "by_module": modules,
        "ready_count": ready_count,
        "total_count": len(download_links),
        "all_ready": ready_count == len(download_links),
    }


@app.get(
    "/outputs/download",
    tags=["产物查看"],
    summary="下载指定产物文件",
    description=(
        "按 key 下载单个输出文件（JSON / PDF / PNG / JPG / JSONL 等）。"
        "key 列表见 GET /outputs/links。演示可直接使用默认 example 参数。"
    ),
)
def download_output_file(
    key: str = Query(
        ...,
        description="产物唯一标识，完整列表见 GET /outputs/links 返回的 files[].key",
        examples={
            "gp答复PDF": {"summary": "超级 GP 协作专业答复", "value": "taskagent_a3_GP协作专业答复"},
            "实践图谱JPG": {"summary": "照护科学实践图谱", "value": DEMO_DOWNLOAD_KEY_ALT},
            "健康计算图JSON": {"summary": "长者健康计算图", "value": "data_agent1_graph_json"},
            "A0序贯配图": {"summary": "序贯事件进展图", "value": "a0_staging_event_png"},
        },
        json_schema_extra={"example": DEMO_DOWNLOAD_KEY},
    ),
):
    """下载指定 key 对应的输出文件。"""
    file_path = _resolve_download_file(key)
    media_types = {
        ".json": "application/json",
        ".pdf": "application/pdf",
        ".md": "text/markdown; charset=utf-8",
        ".png": "image/png",
        ".jpg": "image/jpeg",
    }
    media_type = media_types.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=file_path.name,
    )


@app.get(
    "/jobs",
    tags=["任务查询"],
    summary="列出最近任务",
    description="按时间倒序返回最近的后台任务记录，含 status、耗时、stdout_tail 等。默认返回 20 条。",
)
def list_jobs(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
        description="返回任务条数上限",
        examples=[20],
    ),
) -> List[Dict[str, Any]]:
    return _load_jobs()[:limit]


@app.get(
    "/jobs/{job_id}",
    tags=["任务查询"],
    summary="查询单个任务详情",
    description=(
        "轮询全链路或单模块任务进度。status 取值：pending / running / success / failed。"
        "全链路任务含 sub_steps 逐步状态；成功后 output_paths 列出已生成文件。"
    ),
)
def get_job(
    job_id: str = ApiPath(
        ...,
        description="任务 ID，由 POST /run/pipeline/all 或各 /run/* 接口返回",
        examples=["a1b2c3d4e5f6"],
    ),
) -> Dict[str, Any]:
    job_path = JOB_DIR / f"{job_id}.json"
    if not job_path.is_file():
        raise HTTPException(status_code=404, detail="任务不存在")
    return json.loads(job_path.read_text(encoding="utf-8"))


@app.post(
    "/run/data-agent1",
    tags=["模块运行"],
    summary="运行长者智能计算图 DataAgent",
    description="解析陈女士 CareCase Excel，生成长者健康计算图 JSON 与 PNG。默认 openpyxl 快速模式。",
)
def run_data_agent1(request: StepRunRequest) -> Dict[str, Any]:
    config_status = _check_config()
    if not config_status["ready"]:
        raise HTTPException(status_code=400, detail=config_status)
    job = _start_job("data_agent1", _command_data_agent1(request.parser_mode), PROJECT_ROOT)
    return {"message": "DataAgent1 已启动", "job": job}


@app.post(
    "/run/data-agent2",
    tags=["模块运行"],
    summary="运行三超循证知识基座 DataAgent",
    description="基于健康计算图生成六份 JSONL 训练语料与 batch_summary.json。需先完成 DataAgent1。",
)
def run_data_agent2() -> Dict[str, Any]:
    config_status = _check_config()
    if not config_status["ready"]:
        raise HTTPException(status_code=400, detail=config_status)
    if not DEFAULT_GRAPH.is_file():
        raise HTTPException(status_code=400, detail="请先运行 DataAgent1 生成健康计算图")
    job = _start_job("data_agent2", _command_data_agent2(), PROJECT_ROOT)
    return {"message": "DataAgent2 已启动", "job": job}


@app.post(
    "/run/staging",
    tags=["模块运行"],
    summary="运行序贯分期与贝叶斯推断",
    description="A0 本地流水线：SuStaIn 序贯分期 + 贝叶斯后验计算，纯本地、无需 LLM。",
)
def run_staging() -> Dict[str, Any]:
    job = _start_job("staging", _command_staging(), TASK_AGENT_ROOT)
    return {"message": "序贯分期与贝叶斯流水线已启动", "job": job}


@app.post(
    "/run/staging/visualizations",
    tags=["模块运行"],
    summary="生成 A0 序贯分期配图",
    description="基于分期结果生成序贯事件图、热图、进展曲线、贝叶斯先验后验图共 4 张 PNG。",
)
def run_staging_visualizations() -> Dict[str, Any]:
    job = _start_job("staging_viz", _command_staging_viz(), TASK_AGENT_ROOT)
    return {"message": "A0 配图生成已启动", "job": job}


@app.post(
    "/run/task-agent/demo",
    tags=["模块运行"],
    summary="运行超级 GP（A3）演示",
    description="协同智能体演示模式：仅运行 A3 CDA Hub，约 1–3 分钟，答辩推荐。",
)
def run_task_agent_demo() -> Dict[str, Any]:
    config_status = _check_config()
    if not config_status["ready"]:
        raise HTTPException(status_code=400, detail=config_status)
    job = _start_job("task_agent_a3_demo", _command_task_agent_demo(), TASK_AGENT_ROOT)
    return {"message": "超级 GP（A3）演示任务已启动", "job": job}


@app.post(
    "/run/task-agent/full",
    tags=["模块运行"],
    summary="运行 A1–A14 全量协同",
    description="完整协同智能体链路，产出 17 份 PDF、D30 语料与照护科学实践图谱，耗时较长。",
)
def run_task_agent_full() -> Dict[str, Any]:
    config_status = _check_config()
    if not config_status["ready"]:
        raise HTTPException(status_code=400, detail=config_status)
    job = _start_job("task_agent_full", _command_task_agent_full(), TASK_AGENT_ROOT)
    return {"message": "A1–A14 全量协同任务已启动（耗时较长）", "job": job}


@app.post(
    "/run/pipeline/all",
    tags=["全链路运行"],
    summary="一键运行四大模块（推荐）",
    description=(
        "后台顺序执行：DataAgent1 → DataAgent2 → 序贯贝叶斯 → 协同智能体。"
        "默认 fast_mode=true、demo_task_agent=true，直接 Execute 即可。"
        "返回 job_id 后轮询 GET /jobs/{job_id} 直至 status=success。"
    ),
)
def run_pipeline_all(request: PipelineRunRequest, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    config_status = _check_config()
    if not config_status["ready"]:
        raise HTTPException(status_code=400, detail=config_status)

    job = _create_job("pipeline_all", ["sequential", "四大模块"])
    with _jobs_lock:
        _jobs[job["job_id"]] = job
    background_tasks.add_task(_run_pipeline_background, job["job_id"], request)
    return {
        "message": "全链路流水线已在后台启动",
        "job_id": job["job_id"],
        "poll_url": f"/jobs/{job['job_id']}",
        "fast_mode": request.fast_mode,
        "skip_task_agent": request.skip_task_agent,
        "demo_task_agent": request.demo_task_agent,
    }
