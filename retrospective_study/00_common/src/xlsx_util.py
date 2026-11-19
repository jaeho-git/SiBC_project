# -*- coding: utf-8 -*-
"""Shared writer for the per-study usable-user workbooks (sheets: 안내, 사용자, 상태_기준).

Counts on the 안내 sheet are COUNTIF/COUNTIFS formulas over the 사용자 sheet, so they follow any edit or filter-free change.
The workbook is user-level: it lives in <study>/01_Results and is never committed.
"""
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as CL

FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="DCE6F1")
TITLE = Font(name=FONT, size=13, bold=True)
BOLD = Font(name=FONT, size=10, bold=True)
BODY = Font(name=FONT, size=10)
NOTE = Font(name=FONT, size=9, italic=True, color="555555")
USERS = "사용자"


def write_workbook(path, title, meta, status_specs, df, date_cols=(), widths=None, site_col="사이트"):
	"""meta: list of (label, text). status_specs: list of (status column header, [(label, meaning), ...]).
	df: one row per user; must contain site_col and every status column."""
	wb = Workbook()
	ws = wb.active
	ws.title = "안내"
	ws["A1"] = title
	ws["A1"].font = TITLE
	r = 3
	for k, v in meta:
		ws.cell(r, 1, k).font = BOLD
		c = ws.cell(r, 2, v)
		c.font = BODY
		c.alignment = Alignment(wrap_text=True, vertical="top")
		r += 1
	cols = list(df.columns)
	site_letter = CL(cols.index(site_col) + 1)
	sites = sorted(df[site_col].dropna().unique())
	for header, labels in status_specs:
		r += 1
		ws.cell(r, 1, f"{header} 인원").font = BOLD
		r += 1
		heads = ["상태", "전체"] + [f"{s}" for s in sites]
		for j, h in enumerate(heads, 1):
			c = ws.cell(r, j, h)
			c.font = BOLD
			c.fill = HEAD_FILL
		first = r + 1
		letter = CL(cols.index(header) + 1)
		rng = f"'{USERS}'!${letter}:${letter}"
		srng = f"'{USERS}'!${site_letter}:${site_letter}"
		for lab, _ in labels:
			r += 1
			ws.cell(r, 1, lab).font = BODY
			ws.cell(r, 2, f"=COUNTIF({rng},$A{r})").font = BODY
			for j, s in enumerate(sites, 3):
				ws.cell(r, j, f'=COUNTIFS({rng},$A{r},{srng},"{s}")').font = BODY
		r += 1
		ws.cell(r, 1, "합계").font = BOLD
		for j in range(2, 3 + len(sites)):
			ws.cell(r, j, f"=SUM({CL(j)}{first}:{CL(j)}{r - 1})").font = BOLD
	r += 2
	ws.cell(r, 1, "이 파일은 사용자 단위 자료입니다. git에 올리거나 외부로 보내지 않습니다.").font = NOTE
	ws.column_dimensions["A"].width = 34
	ws.column_dimensions["B"].width = 90
	for j in range(3, 3 + len(sites)):
		ws.column_dimensions[CL(j)].width = 10

	wu = wb.create_sheet(USERS)
	for j, h in enumerate(cols, 1):
		c = wu.cell(1, j, h)
		c.font = BOLD
		c.fill = HEAD_FILL
		c.alignment = Alignment(wrap_text=True, vertical="center")
	for i, row in enumerate(df.itertuples(index=False), 2):
		for j, v in enumerate(row, 1):
			if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
				continue
			if isinstance(v, pd.Timestamp):
				v = v.to_pydatetime()
			c = wu.cell(i, j, v)
			c.font = BODY
			if cols[j - 1] in date_cols:
				c.number_format = "yyyy-mm-dd"
	wu.freeze_panes = "B2"
	wu.auto_filter.ref = f"A1:{CL(len(cols))}{len(df) + 1}"
	for j, h in enumerate(cols, 1):
		wu.column_dimensions[CL(j)].width = (widths or {}).get(h, max(10, min(28, len(str(h)) * 1.6)))
	wu.column_dimensions["A"].width = 38
	wu.row_dimensions[1].height = 42

	wd = wb.create_sheet("상태_기준")
	for j, h in enumerate(["구분", "상태", "뜻"], 1):
		c = wd.cell(1, j, h)
		c.font = BOLD
		c.fill = HEAD_FILL
	r = 1
	for header, labels in status_specs:
		for lab, meaning in labels:
			r += 1
			wd.cell(r, 1, header).font = BODY
			wd.cell(r, 2, lab).font = BODY
			c = wd.cell(r, 3, meaning)
			c.font = BODY
			c.alignment = Alignment(wrap_text=True, vertical="top")
	wd.column_dimensions["A"].width = 22
	wd.column_dimensions["B"].width = 30
	wd.column_dimensions["C"].width = 90
	wb.save(path)
