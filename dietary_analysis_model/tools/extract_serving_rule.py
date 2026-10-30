"""Extract the processed-food serving rule (1회 섭취참고량) from the portal's .xls download.

	python tools/extract_serving_rule.py --xls "<가공식품 .xls>" --out data/processed_food_serving_rule.csv

The API payload has no 1회 섭취참고량, but the portal's 가공식품 file does, and the
value is fixed per 대표식품 (식약처 식품유형별 1회 섭취참고량). This writes one row per
(대표식품명, 식품중분류명) with the dominant text and a parsed numeric value, so the
rule can be applied to every processed food in the full dataset.
"""

import argparse
import collections
import csv
import re

import xlrd

_QTY = re.compile(r"([\d.]+)\s*(g|ml|mL)")


def parse_rule(text: str, mid_name: str) -> tuple[float | None, str | None]:
	"""'70g' -> (70, 'g'); multi-part text picks the part whose label matches the 중분류 name."""
	text = (text or "").strip()
	if not text:
		return None, None
	parts = re.split(r"[,/]", text)
	if len(parts) > 1:
		for part in parts:
			label = re.sub(r"[\d.]+\s*(g|ml|mL).*", "", part).strip("() ·")
			if label and mid_name and (label in mid_name or any(k in mid_name for k in label.split("·"))):
				m = _QTY.search(part)
				if m:
					return float(m.group(1)), m.group(2).lower()
	m = _QTY.search(text)
	return (float(m.group(1)), m.group(2).lower()) if m else (None, None)


def main() -> None:
	ap = argparse.ArgumentParser()
	ap.add_argument("--xls", required=True)
	ap.add_argument("--out", required=True)
	args = ap.parse_args()
	ws = xlrd.open_workbook(args.xls, on_demand=True).sheet_by_index(0)
	hdr = ws.row_values(1)
	ix = {h: i for i, h in enumerate(hdr)}
	texts: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
	for r in range(2, ws.nrows):
		row = ws.row_values(r)
		t = str(row[ix["1회 섭취참고량"]]).strip()
		if t:
			texts[(row[ix["대표식품명"]], row[ix["식품중분류명"]])][t] += 1
	rows = []
	for (rep, mid), c in sorted(texts.items()):
		text, n = c.most_common(1)[0]
		share = n / sum(c.values())
		qty, unit = parse_rule(text, mid)
		rows.append({"대표식품명": rep, "식품중분류명": mid, "1회섭취참고량_원문": text, "표본수": sum(c.values()),
			"최빈값비율": f"{share:.2f}", "1회량": "" if qty is None else f"{qty:g}", "단위": unit or ""})
	with open(args.out, "w", encoding="utf-8", newline="") as fh:
		w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
		w.writeheader()
		w.writerows(rows)
	parsed = sum(1 for r in rows if r["1회량"])
	print(f"rules: {len(rows)} (parsed numeric: {parsed}) -> {args.out}")


if __name__ == "__main__":
	main()
