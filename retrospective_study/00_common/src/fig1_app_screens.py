# -*- coding: utf-8 -*-
"""Figure 1 of the three manuscripts: app screens from a demonstration account (three panels for studies 01 and 03, two for
study 02), with panel letters and the numbered markers that the figure captions explain. No screen is used in more than one
study.

The screenshots are captured by the app development team and kept in the git-ignored folder 00_common/00_Data/app_screens/,
one file per screen whose name starts with the two-digit screen number (01_*.png ... 09_*.png; see SCREENS). Number 05 is not
used: the app has no checkup result detail screen, so study 02 shows the checkup tab and the home screen only.

Run from retrospective_study/:
  python3 00_common/src/fig1_app_screens.py                  check the screenshots and write fig1_app_screens.png per study
  python3 00_common/src/fig1_app_screens.py --draft          write proof sheets with a coordinate grid to place the markers
  python3 00_common/src/fig1_app_screens.py --mock <folder>  make mock screenshots in <folder> and draw from them (layout test)

Marker positions and crops are set in LAYOUT after looking at the proof sheets. Real names or real health values must never
appear: the screens come from a demonstration account, and MASK regions are available for anything that still must not show."""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "00_common/src"))
import figstyle as FS  # noqa: E402

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

FS.use()
SRC = ROOT / "00_common/00_Data/app_screens"
OUT = {"01": ROOT / "01_wearable_metrics/01_Results/analysis", "02": ROOT / "02_checkup_metrics/01_Results/analysis",
       "03": ROOT / "03_irs_risk_rank/01_Results/analysis"}
NAME = "fig1_app_screens.png"

# Screens requested from the development team (number: what the screen must show).
SCREENS = {
	1: "건강 데이터 연동 탭: 연동된 출처와 연동 상태",
	2: "건강 모니터링 주간 화면 위쪽: 주·요일 선택, 최근 동기화 시각, 걸음·수면·운동·심박 카드, 운동 기록 없는 날 \"–\"",
	3: "건강 모니터링 주간 화면 아래쪽: 체중·혈당·혈압 카드와 측정일",
	4: "건강검진 탭: 탭 목록, 건강검진 탭 선택, 연계된 검진과 검진일",
	6: "홈 화면: 팝업 없음, 건강활동점수, 포인트, 아래 메뉴",
	7: "건강 취약도 TOP 3: 질환별 1~100 점수, 의학적 진단이 아님 안내",
	8: "건강 취약도 결과: 구간 범례와 질환 수, 현재·이전 계산 막대, 구간이 내려간 질환과 올라간 질환",
	9: "생활설문 탭: 응답일, 다시하기 버튼",
}

# Panels per study: (screen number, panel title, marker numbers explained in the caption). Accent = marker colour.
STUDY = {
	"01": dict(accent=FS.S01["high"], panels=[(1, "Data linkage", [1]), (2, "Weekly monitoring", [1, 2]), (3, "Device measurements", [1])]),
	"02": dict(accent=FS.S02_ITEM, panels=[(4, "Health checkup tab", [1, 2, 3]), (6, "Home screen", [1, 2, 3])]),
	"03": dict(accent=FS.S03["high"], panels=[(7, "Top 3 disease groups", [1, 2]), (8, "Vulnerability results", [1, 2, 3]), (9, "Lifestyle survey", [1, 2])]),
}

# Per screen, set after looking at the proof sheets (all values are fractions of the image):
#   crop    (top, bottom) of the original image to keep; top removes the status bar. None uses the defaults below.
#   markers {number: (x, y)} centre of each numbered marker on the cropped image. None means not yet placed.
#   masks   [(x0, y0, x1, y1)] regions on the cropped image filled with a flat colour.
#   file    exact file name when the folder holds more than one file for the screen.
STATUS_BAR = 0.06
LAYOUT = {n: dict(crop=(None, None), markers={}, masks=[], file=None) for n in SCREENS}
# The delivered screenshots (860 x 1864, one device) start below the status bar, so nothing is cropped. Screen 2 is the
# weekly screen with a day without an exercise record selected; screen 3 is the lower part of the same week with another
# day selected. Marker centres were placed on the proof sheets, in blank space next to the element each caption names.
for _n in SCREENS:
	LAYOUT[_n]["crop"] = (0.0, 1.0)
LAYOUT[1]["markers"] = {1: (0.56, 0.337)}                                   # linked source and linkage status
LAYOUT[2]["markers"] = {1: (0.20, 0.265), 2: (0.20, 0.711)}                 # last synchronization; exercise "-"
LAYOUT[3]["markers"] = {1: (0.75, 0.218)}                                   # measurement date (weight)
LAYOUT[4]["markers"] = {1: (0.436, 0.182), 2: (0.62, 0.216), 3: (0.12, 0.862)}  # tab; linked result; retrieve button
LAYOUT[6]["markers"] = {1: (0.80, 0.46), 2: (0.70, 0.203), 3: (0.21, 0.955)}    # activity score; points; bottom menu
LAYOUT[7]["markers"] = {1: (0.70, 0.298), 2: (0.88, 0.224)}                 # group score; not-a-diagnosis notice
LAYOUT[8]["markers"] = {1: (0.10, 0.287), 2: (0.30, 0.635), 3: (0.33, 0.789)}   # categories (below the table); moved up; moved down
LAYOUT[9]["markers"] = {1: (0.68, 0.229), 2: (0.12, 0.862)}                 # response date; retake button

PANEL_W = 2.75  # inches per phone screen
GAP = 0.42
TOP = 0.42
CORNER = 0.035  # rounded corner radius as a fraction of the panel width


def find(n, src):
	files = sorted(p for p in src.glob(f"{n:02d}_*") if p.suffix.lower() in {".png", ".jpg", ".jpeg"})
	want = LAYOUT[n]["file"]
	if want:
		files = [p for p in files if p.name == want]
	return files


def check(src):
	"""Every screen present, one file each, same device size. Returns {number: path}."""
	paths, missing, sizes = {}, [], {}
	for n in SCREENS:
		f = find(n, src)
		if not f:
			missing.append(n); continue
		if len(f) > 1:
			print(f"  screen {n:02d}: {len(f)} files ({', '.join(p.name for p in f)}); using {f[0].name}. Set LAYOUT[{n}]['file'] to choose.")
		paths[n] = f[0]
		sizes[n] = Image.open(f[0]).size
	if missing:
		print("missing screenshots in", src)
		for n in missing:
			print(f"  {n:02d}_*.png  {SCREENS[n]}")
	widths = {w for w, _ in sizes.values()}
	if len(widths) > 1:
		print("  warning: screenshots differ in width, so they may come from different devices:",
		      ", ".join(f"{n:02d}={w}x{h}" for n, (w, h) in sizes.items()))
	return paths, missing


def load(n, path):
	im = np.asarray(Image.open(path).convert("RGB"))
	h = im.shape[0]
	top, bottom = LAYOUT[n]["crop"]
	top = STATUS_BAR if top is None else top
	bottom = 1.0 if bottom is None else bottom
	return im[int(round(top * h)):int(round(bottom * h))]


def draw_study(study, paths, out, draft=False):
	cfg = STUDY[study]
	ims = [load(n, paths[n]) for n, _, _ in cfg["panels"]]
	heights = [PANEL_W * im.shape[0] / im.shape[1] for im in ims]
	n_panels = len(cfg["panels"])
	fig_w = n_panels * PANEL_W + (n_panels - 1) * GAP + 0.1
	fig_h = max(heights) + TOP + 0.1
	fig = plt.figure(figsize=(fig_w, fig_h))
	unplaced = []
	for k, ((n, title, nums), im, hh) in enumerate(zip(cfg["panels"], ims, heights)):
		x0 = 0.05 + k * (PANEL_W + GAP)
		ax = fig.add_axes([x0 / fig_w, (fig_h - TOP - hh) / fig_h, PANEL_W / fig_w, hh / fig_h])
		H, W = im.shape[:2]
		shown = ax.imshow(im, extent=(0, W, H, 0), interpolation="lanczos")
		r = CORNER * W
		frame = FancyBboxPatch((0, 0), W, H, boxstyle=f"round,pad=0,rounding_size={r}", fc="none", ec=FS.INK2, lw=1.1,
		                       transform=ax.transData, zorder=3)
		ax.add_patch(frame); shown.set_clip_path(frame)
		for (mx0, my0, mx1, my1) in LAYOUT[n]["masks"]:
			ax.add_patch(Rectangle((mx0 * W, my0 * H), (mx1 - mx0) * W, (my1 - my0) * H, fc=FS.NEUTRAL, ec="none", zorder=2))
		if draft:
			for g in np.arange(0.1, 1.0, 0.1):
				ax.axvline(g * W, color="#d03b3b", lw=0.4, alpha=0.7); ax.axhline(g * H, color="#d03b3b", lw=0.4, alpha=0.7)
				ax.text(g * W, 0.01 * H, f"{g:.1f}", color="#d03b3b", fontsize=5, ha="center", va="top")
				ax.text(0.01 * W, g * H, f"{g:.1f}", color="#d03b3b", fontsize=5, ha="left", va="center")
		for j, m in enumerate(nums):
			pos = LAYOUT[n]["markers"].get(m)
			if pos is None:
				unplaced.append(f"screen {n:02d} marker {m}")
				if not draft:
					continue
				pos = (0.93, 0.08 + 0.07 * j)
			ax.text(pos[0] * W, pos[1] * H, str(m), ha="center", va="center", color="white",
			        fontsize=8.5, fontweight="bold", zorder=5,
			        bbox=dict(boxstyle="circle,pad=0.28", fc=cfg["accent"] if LAYOUT[n]["markers"].get(m) else "#d03b3b",
			                  ec="white", lw=1.3))
		ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis("off")
		fig.text(x0 / fig_w, (fig_h - 0.12) / fig_h, f"{'ABC'[k]}  {title}", ha="left", va="top", fontsize=9.5,
		         fontweight="bold", color=FS.INK)
	if unplaced and not draft:
		plt.close(fig)
		raise SystemExit(f"{study}: markers not yet placed ({'; '.join(unplaced)}). Run with --draft and set LAYOUT.")
	out.parent.mkdir(parents=True, exist_ok=True)
	fig.savefig(out, facecolor="white", dpi=300); plt.close(fig)
	print("wrote", out, "(unplaced: " + ", ".join(unplaced) + ")" if unplaced else "")


def make_mock(folder):
	"""Grey phone-sized mock screens with a fake status bar, for layout tests only."""
	folder.mkdir(parents=True, exist_ok=True)
	try:
		font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 64)
	except OSError:
		font = ImageFont.load_default()
	for n in SCREENS:
		im = Image.new("RGB", (1179, 2556), (246, 246, 243)); d = ImageDraw.Draw(im)
		d.rectangle([0, 0, 1179, 150], fill=(210, 210, 205)); d.text((40, 50), "status bar", fill=(90, 90, 90), font=font)
		for i in range(6):
			y = 260 + i * 360
			d.rounded_rectangle([60, y, 1119, y + 300], radius=36, fill=(255, 255, 255), outline=(220, 220, 214), width=3)
			d.text((100, y + 40), f"mock screen {n:02d}  card {i + 1}", fill=(120, 120, 120), font=font)
		im.save(folder / f"{n:02d}_mock.png")
	for n, cfg in LAYOUT.items():  # spread markers so that the layout can be judged
		nums = next(p[2] for s in STUDY.values() for p in s["panels"] if p[0] == n)
		cfg["markers"] = {m: (0.85, 0.15 + 0.14 * j) for j, m in enumerate(nums)}


def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("--draft", action="store_true")
	ap.add_argument("--mock", type=Path)
	a = ap.parse_args()
	src = SRC
	if a.mock:
		make_mock(a.mock); src = a.mock
	paths, missing = check(src)
	if missing:
		raise SystemExit(1)
	for study in STUDY:
		if a.mock:
			out = a.mock / f"fig1_app_screens_{study}.png"
		elif a.draft:
			out = SRC / "proof" / f"fig1_proof_{study}.png"
		else:
			out = OUT[study] / NAME
		draw_study(study, paths, out, draft=a.draft)


if __name__ == "__main__":
	main()
