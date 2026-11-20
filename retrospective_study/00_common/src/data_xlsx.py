# -*- coding: utf-8 -*-
"""Shared writer for the per-study analysis-data and app-usage workbooks (user-level values, never committed).

Sheets: 안내 (meta rows), 열_설명 (one row per data column), then the data sheets in the given order.
Write-only mode keeps memory low for the long day-level sheets.
"""
import datetime as dt

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font, PatternFill

FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="DCE6F1")
TITLE = Font(name=FONT, size=13, bold=True)
BOLD = Font(name=FONT, size=10, bold=True)
BODY = Font(name=FONT, size=10)
NOTE = Font(name=FONT, size=9, italic=True, color="555555")
WRAP = Alignment(wrap_text=True, vertical="top")


def _value(v):
	"""Cell value for openpyxl; None for any missing marker."""
	if v is None or v is pd.NaT:
		return None
	if isinstance(v, float) and np.isnan(v):
		return None
	if v is pd.NA:
		return None
	if isinstance(v, pd.Timestamp):
		return v.to_pydatetime()
	if isinstance(v, np.integer):
		return int(v)
	if isinstance(v, np.floating):
		return None if np.isnan(v) else float(v)
	if isinstance(v, np.bool_):
		return bool(v)
	return v


def write_data_workbook(path, title, meta, sheets, coldoc):
	"""meta: [(label, text)]. sheets: [(name, DataFrame, set of date columns, {column: width})].
	coldoc: [(sheet, column, meaning)]; every data column must be documented."""
	documented = {(s, c) for s, c, _ in coldoc}
	for name, df, _, _ in sheets:
		missing = [c for c in df.columns if (name, c) not in documented]
		if missing:
			raise SystemExit(f"undocumented columns in {name}: {missing}")
	wb = Workbook(write_only=True)

	def cell(ws, v, font=BODY, fill=None, fmt=None, align=None):
		v = _value(v)
		c = WriteOnlyCell(ws, value=v)
		if isinstance(v, str):
			c.data_type = "s"  # keep source text literal (a value starting with "=" must not become a formula)
		c.font = font
		if fill is not None:
			c.fill = fill
		if fmt:
			c.number_format = fmt
		if align is not None:
			c.alignment = align
		return c

	ws = wb.create_sheet("안내")
	ws.column_dimensions["A"].width = 30
	ws.column_dimensions["B"].width = 110
	ws.append([cell(ws, title, TITLE)])
	ws.append([])
	for k, v in meta:
		ws.append([cell(ws, k, BOLD, align=WRAP), cell(ws, v, align=WRAP)])
	ws.append([])
	ws.append([cell(ws, "시트", BOLD, HEAD_FILL), cell(ws, "행 수", BOLD, HEAD_FILL)])
	for name, df, _, _ in sheets:
		ws.append([cell(ws, name), cell(ws, len(df))])
	ws.append([])
	ws.append([cell(ws, "이 파일은 사용자 단위 건강 자료입니다. git에 올리거나 외부로 보내지 않습니다.", NOTE)])

	wd = wb.create_sheet("열_설명")
	for col, w in zip("ABC", (18, 30, 100)):
		wd.column_dimensions[col].width = w
	wd.append([cell(wd, h, BOLD, HEAD_FILL) for h in ["시트", "열", "뜻"]])
	for s, c, m in coldoc:
		wd.append([cell(wd, s), cell(wd, c), cell(wd, m, align=WRAP)])

	for name, df, dates, widths in sheets:
		w = wb.create_sheet(name)
		cols = list(df.columns)
		for j, h in enumerate(cols):
			letter = _letter(j + 1)
			w.column_dimensions[letter].width = (widths or {}).get(h, 38 if h == "user_id" else max(10, min(26, len(str(h)) * 1.5)))
		w.freeze_panes = "B2"
		w.append([cell(w, h, BOLD, HEAD_FILL, align=Alignment(wrap_text=True, vertical="center")) for h in cols])
		date_idx = {j for j, h in enumerate(cols) if h in dates}
		for row in df.itertuples(index=False, name=None):
			w.append([cell(w, v, fmt="yyyy-mm-dd" if j in date_idx else None) for j, v in enumerate(row)])
	wb.save(path)


def _letter(n):
	s = ""
	while n:
		n, r = divmod(n - 1, 26)
		s = chr(65 + r) + s
	return s


def yn(mask):
	"""Boolean Series -> 예/아니오 text column."""
	return np.where(mask, "예", "아니오")


def today():
	return dt.date.today().isoformat()
