"""Download the full 전국통합식품영양성분정보 표준데이터 from data.go.kr.

	export DATAGO_KEY=<service key>
	python tools/download_nutri_std.py --out "/Users/.../전국통합식품영양성분정보_전체.csv"

Pages through tn_pubr_public_nutri_info_api (1,000 rows per page, the API
maximum), retries transient failures, and resumes from a checkpoint file next
to the output. Column headers follow the portal's Korean file layout so the
CSV lines up with the manually downloaded .xls files.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ENDPOINT = "https://api.data.go.kr/openapi/tn_pubr_public_nutri_info_api"
PAGE_SIZE = 1000

# API field -> Korean column name used by the portal's file download
COLUMNS = [
	("foodCd", "식품코드"), ("foodNm", "식품명"), ("dataCd", "데이터구분코드"), ("typeNm", "데이터구분명"),
	("enerc", "에너지(kcal)"), ("nutConSrtrQua", "영양성분함량기준량"), ("water", "수분(g)"),
	("prot", "단백질(g)"), ("fatce", "지방(g)"), ("ash", "회분(g)"), ("chocdf", "탄수화물(g)"),
	("sugar", "당류(g)"), ("fibtg", "식이섬유(g)"), ("ca", "칼슘(mg)"), ("fe", "철(mg)"), ("p", "인(mg)"),
	("k", "칼륨(mg)"), ("nat", "나트륨(mg)"), ("vitaRae", "비타민 A(μg RAE)"), ("retol", "레티놀(μg)"),
	("cartb", "베타카로틴(μg)"), ("thia", "티아민(mg)"), ("ribf", "리보플라빈(mg)"), ("nia", "니아신(mg)"),
	("vitc", "비타민 C(mg)"), ("vitd", "비타민 D(μg)"), ("chole", "콜레스테롤(mg)"), ("fasat", "포화지방산(g)"),
	("fatrn", "트랜스지방산(g)"), ("refuse", "폐기율(%)"), ("srcCd", "출처코드"), ("srcNm", "출처명"),
	("foodSize", "식품중량"), ("imptYn", "수입여부"), ("cooCd", "원산지국코드"), ("cooNm", "원산지국명"),
	("itemMnftrRptNo", "품목제조보고번호"), ("companyNm", "업체명"), ("mkrNm", "제조사명"),
	("imptrNm", "수입업체명"), ("rtlBzentyNm", "유통업체명"), ("dataProdCd", "데이터생성방법코드"),
	("dataProdNm", "데이터생성방법명"), ("crtYmd", "데이터생성일자"), ("crtrYmd", "데이터기준일자"),
	("insttCode", "제공기관코드"), ("insttNm", "제공기관명"),
]


def fetch_page(key: str, page: int, retries: int = 5) -> tuple[list[dict], int]:
	url = ENDPOINT + "?" + urllib.parse.urlencode(
		{"serviceKey": key, "pageNo": page, "numOfRows": PAGE_SIZE, "type": "json"})
	for attempt in range(1, retries + 1):
		try:
			with urllib.request.urlopen(url, timeout=120) as r:
				body = json.loads(r.read().decode("utf-8", "replace"))
			hdr = body.get("header", {})
			if hdr.get("resultCode") != "00":
				raise RuntimeError(f"API error {hdr}")
			b = body["body"]
			items = b.get("items") or {}
			rows = items.get("item", []) if isinstance(items, dict) else []
			return rows, int(b.get("totalCount", 0))
		except Exception as e:  # noqa: BLE001 - retry any transient failure
			if attempt == retries:
				raise
			time.sleep(2 * attempt)
			print(f"page {page}: retry {attempt} after {type(e).__name__}: {str(e)[:100]}", file=sys.stderr)
	return [], 0


def main() -> None:
	ap = argparse.ArgumentParser()
	ap.add_argument("--out", required=True, help="output CSV path")
	ap.add_argument("--sleep", type=float, default=0.2, help="seconds between requests")
	args = ap.parse_args()
	key = os.environ["DATAGO_KEY"]
	ckpt = args.out + ".page"
	start = 1
	mode = "w"
	if os.path.exists(ckpt) and os.path.exists(args.out):
		start = int(open(ckpt).read().strip() or 0) + 1
		mode = "a"
	with open(args.out, mode, encoding="utf-8-sig", newline="") as fh:
		w = csv.writer(fh)
		if mode == "w":
			w.writerow([ko for _, ko in COLUMNS])
		page = start
		total = None
		written = 0
		while True:
			rows, total = fetch_page(key, page)
			if not rows:
				break
			for r in rows:
				w.writerow([r.get(api, "") for api, _ in COLUMNS])
			written += len(rows)
			fh.flush()
			open(ckpt, "w").write(str(page))
			if page % 25 == 0 or page * PAGE_SIZE >= total:
				print(f"page {page}: {page * PAGE_SIZE if page * PAGE_SIZE < total else total}/{total}", flush=True)
			if page * PAGE_SIZE >= total:
				break
			page += 1
			time.sleep(args.sleep)
	print(f"done: wrote {written} rows this run (total reported {total}) -> {args.out}")


if __name__ == "__main__":
	main()
