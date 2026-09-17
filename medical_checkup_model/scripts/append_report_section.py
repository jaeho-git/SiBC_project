#!/usr/bin/env python3
"""기존 보고서 docx에 결과 장(章)을 OOXML 수준에서 삽입한다 (영속 스크립트).

- 기존 문서의 서식 템플릿(Pretendard, Heading1/2, 본문, 글머리(numId=2), 강조상자, 표)을 그대로 복제
- 지정 제목(예: "11. ")으로 시작하는 기존 장이 있으면 '부록 A' 직전까지 제거 후 교체(멱등)
- 삽입 위치: '부록 A'로 시작하는 Heading1 직전
사용: python scripts/append_report_section.py <docx> <section.json> [--out <docx>]
section.json: {"title": "11. ...", "blocks": [{"type": "h2"|"body"|"bullets"|"note"|"table", ...}]}
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

FONT = '<w:rFonts w:ascii="Pretendard" w:cs="Pretendard" w:eastAsia="Pretendard" w:hAnsi="Pretendard"/>'


def _run(text: str, sz: int, bold: bool = False, color: str | None = None) -> str:
    b = "<w:b/><w:bCs/>" if bold else '<w:b w:val="false"/><w:bCs w:val="false"/>'
    c = f'<w:color w:val="{color}"/>' if color else ""
    return (f'<w:r><w:rPr>{FONT}{b}{c}<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>'
            f'<w:t xml:space="preserve">{escape(text)}</w:t></w:r>')


def h1(text: str) -> str:
    return (f'<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:spacing w:before="280" w:after="140"/></w:pPr>'
            f'{_run(text, 30, True, "1F4E79")}</w:p>')


def h2(text: str) -> str:
    return (f'<w:p><w:pPr><w:pStyle w:val="Heading2"/><w:spacing w:before="200" w:after="100"/></w:pPr>'
            f'{_run(text, 24, True, "333333")}</w:p>')


def body(text: str) -> str:
    return f'<w:p><w:pPr><w:spacing w:after="120" w:line="300"/></w:pPr>{_run(text, 20)}</w:p>'


def bullet(text: str) -> str:
    return (f'<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr>'
            f'<w:spacing w:after="60" w:line="280"/></w:pPr>{_run(text, 20)}</w:p>')


def note(text: str) -> str:
    return (f'<w:p><w:pPr><w:pBdr><w:left w:val="single" w:color="E8A33D" w:sz="18"/></w:pBdr>'
            f'<w:shd w:fill="FDF2E3" w:val="clear"/><w:spacing w:before="100" w:after="160"/><w:ind w:left="120"/></w:pPr>'
            f'{_run(text, 20)}</w:p>')


def table(header: list[str], rows: list[list[str]], widths: list[int] | None = None, sz: int = 18) -> str:
    total = 9360
    n = len(header)
    widths = widths or [total // n] * n
    scale = total / sum(widths)
    widths = [int(w * scale) for w in widths]

    def cell(text, w, head):
        shd = '<w:shd w:fill="DCE6F1" w:val="clear"/>' if head else ""
        return (f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="{w}"/>{shd}</w:tcPr>'
                f'<w:p><w:pPr><w:spacing w:before="30" w:after="30"/><w:jc w:val="left"/></w:pPr>'
                f'{_run(str(text), sz, head)}</w:p></w:tc>')

    borders = "".join(f'<w:{k} w:val="single" w:color="auto" w:sz="4"/>'
                      for k in ("top", "left", "bottom", "right", "insideH", "insideV"))
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    hdr = '<w:tr><w:trPr><w:tblHeader/></w:trPr>' + "".join(cell(t, w, True) for t, w in zip(header, widths)) + "</w:tr>"
    data = "".join('<w:tr><w:trPr><w:cantSplit/></w:trPr>' + "".join(cell(t, w, False) for t, w in zip(r, widths)) + "</w:tr>"
                   for r in rows)
    spacer = '<w:p><w:pPr><w:spacing w:after="120"/></w:pPr></w:p>'
    return (f'<w:tbl><w:tblPr><w:tblW w:type="dxa" w:w="{total}"/><w:tblBorders>{borders}</w:tblBorders></w:tblPr>'
            f'<w:tblGrid>{grid}</w:tblGrid>{hdr}{data}</w:tbl>{spacer}')


def render(spec: dict) -> str:
    out = [h1(spec["title"])]
    for b in spec["blocks"]:
        t = b["type"]
        if t == "h2":
            out.append(h2(b["text"]))
        elif t == "body":
            out.append(body(b["text"]))
        elif t == "note":
            out.append(note(b["text"]))
        elif t == "bullets":
            out.extend(bullet(x) for x in b["items"])
        elif t == "table":
            out.append(table(b["header"], b["rows"], b.get("widths"), b.get("sz", 18)))
        else:
            raise ValueError(f"unknown block type: {t}")
    return "".join(out)


def _para_text(p: str) -> str:
    return "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p))


def splice(document_xml: str, section_xml: str, title_prefix: str, before_prefix: str = "부록 A") -> str:
    head, body_xml, tail = document_xml.partition("<w:body>")[0] + "<w:body>", None, None
    start = document_xml.find("<w:body>") + len("<w:body>")
    end = document_xml.rfind("</w:body>")
    body_xml, tail = document_xml[start:end], document_xml[end:]
    items = re.findall(r"(<w:p[ >].*?</w:p>|<w:tbl>.*?</w:tbl>|<w:sectPr.*?</w:sectPr>)", body_xml, flags=re.S)
    assert "".join(items) == body_xml, "body tokenization mismatch"

    def is_h1(it, prefix):
        return it.startswith("<w:p") and 'w:val="Heading1"' in it and _para_text(it).startswith(prefix)

    # 기존 동일 장 제거 (멱등)
    i = next((k for k, it in enumerate(items) if is_h1(it, title_prefix)), None)
    if i is not None:
        j = next((k for k in range(i + 1, len(items)) if is_h1(items[k], before_prefix)), len(items) - 1)
        items = items[:i] + items[j:]
    j = next((k for k, it in enumerate(items) if is_h1(it, before_prefix)), None)
    if j is None:
        raise RuntimeError(f"insertion anchor not found: Heading1 starting with {before_prefix!r}")
    items.insert(j, section_xml)
    return head + "".join(items) + tail


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("docx"); ap.add_argument("section_json"); ap.add_argument("--out", default=None)
    a = ap.parse_args()
    src, out = Path(a.docx), Path(a.out or a.docx)
    spec = json.loads(Path(a.section_json).read_text(encoding="utf-8"))
    title_prefix = spec["title"].split(" ")[0] + " "  # "11. "
    tmp = out.with_suffix(".tmp.docx")
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                data = splice(data.decode("utf-8"), render(spec), title_prefix).encode("utf-8")
            zout.writestr(item, data)
    shutil.move(tmp, out)
    print(f"wrote {out} (+ section {spec['title']!r})")


if __name__ == "__main__":
    main()
