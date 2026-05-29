#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 output 目录下 PDF 转为同名 Markdown（仅正文，无来源/转换时间元数据）。"""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def safe_text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def extract_pdf_body(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    page_texts: list[str] = []
    for page in reader.pages:
        text = safe_text(page.extract_text())
        if text:
            page_texts.append(text)
    body = "\n\n".join(page_texts)
    body = re.sub(r"\r\n?", "\n", body)
    return body.strip()


def strip_pdf_page_header(text: str) -> str:
    """去掉 PDF 页眉中的标题行与「生成时间」行。"""
    lines = text.splitlines()
    cleaned: list[str] = []
    skipped_header = False
    for line in lines:
        stripped = line.strip()
        if not skipped_header:
            if re.match(r"^生成时间[:：]", stripped):
                skipped_header = True
                continue
            # 首页首行常为与文档同名的短标题，跳过
            if not cleaned and len(stripped) < 40 and "：" not in stripped and "**" not in stripped:
                continue
            skipped_header = True
        cleaned.append(line)
    body = "\n".join(cleaned).strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body


def build_markdown_from_pdf(pdf_path: Path) -> str:
    body = strip_pdf_page_header(extract_pdf_body(pdf_path))
    return (body or "（未能从 PDF 抽取文本）") + "\n"


def convert_all(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for pdf_path in sorted(output_dir.glob("*.pdf")):
        md_path = pdf_path.with_suffix(".md")
        md_path.write_text(build_markdown_from_pdf(pdf_path), encoding="utf-8")
        written.append(md_path)
        print(f"OK  {pdf_path.name} -> {md_path.name}")
    return written


if __name__ == "__main__":
    paths = convert_all()
    print(f"\n共转换 {len(paths)} 个文件，目录：{OUTPUT_DIR}")
