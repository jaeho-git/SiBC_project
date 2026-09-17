#!/usr/bin/env python3
"""보고서 docx의 표 행/문장 텍스트를 OOXML 수준에서 교체한다 (영속 스크립트, 멱등).

spec.json:
{
  "rows": [{"match": "<행을 식별할 첫 셀 텍스트(정확히 일치)>", "cells": ["새 셀1", "새 셀2", ...]}],
  "texts": [{"old": "<런 내 부분 문자열>", "new": "<대체 문자열>"}]
}
- rows: match 텍스트를 가진 셀이 속한 <w:tr>의 각 셀 첫 런 텍스트를 순서대로 교체(셀 수만큼)
- texts: 모든 <w:t> 런에서 부분 문자열 교체
사용: python scripts/patch_report_rows.py <docx> <spec.json>
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

T_RE = re.compile(r"(<w:t(?: [^>]*)?>)(.*?)(</w:t>)", re.S)


def _set_first_run_text(cell_xml: str, new_text: str) -> str:
    done = False

    def rep(m):
        nonlocal done
        if done:
            return m.group(1) + m.group(3)  # 이후 런 텍스트는 비움
        done = True
        return m.group(1) + escape(new_text) + m.group(3)

    return T_RE.sub(rep, cell_xml)


def patch(document_xml: str, spec: dict) -> tuple[str, list[str]]:
    log = []
    for row in spec.get("rows", []):
        match, cells = row["match"], row["cells"]
        found = False
        for tr in re.findall(r"<w:tr[ >].*?</w:tr>", document_xml, flags=re.S):
            texts = ["".join(T_RE.findall(tc)[i][1] for i in range(len(T_RE.findall(tc)))) for tc in
                     re.findall(r"<w:tc>.*?</w:tc>", tr, flags=re.S)]
            if texts and texts[0] == match:
                tcs = re.findall(r"<w:tc>.*?</w:tc>", tr, flags=re.S)
                new_tcs = [_set_first_run_text(tc, cells[i]) if i < len(cells) else tc
                           for i, tc in enumerate(tcs)]
                new_tr = tr
                for old, new in zip(tcs, new_tcs):
                    new_tr = new_tr.replace(old, new, 1)
                document_xml = document_xml.replace(tr, new_tr, 1)
                log.append(f"row replaced: {match!r} ({min(len(cells), len(tcs))} cells)")
                found = True
                break
        if not found:
            log.append(f"row NOT found: {match!r}")
    for t in spec.get("texts", []):
        n = 0

        def rep(m):
            nonlocal n
            if t["old"] in m.group(2):
                n += 1
                return m.group(1) + m.group(2).replace(t["old"], escape(t["new"])) + m.group(3)
            return m.group(0)

        document_xml = T_RE.sub(rep, document_xml)
        log.append(f"text {t['old']!r}: {n} run(s) replaced")
    return document_xml, log


def main() -> None:
    docx, spec_path = Path(sys.argv[1]), Path(sys.argv[2])
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    tmp = docx.with_suffix(".tmp.docx")
    with zipfile.ZipFile(docx) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == "word/document.xml":
                xml, log = patch(data.decode("utf-8"), spec)
                data = xml.encode("utf-8")
                print("\n".join(log))
            zout.writestr(item, data)
    shutil.move(tmp, docx)
    print(f"wrote {docx}")


if __name__ == "__main__":
    main()
