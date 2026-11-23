# -*- coding: utf-8 -*-
"""Shared figure style for the three manuscripts: one quiet chart chrome, and a different accent palette per study so that the
three papers do not look alike. Colour pairs were checked for colour-vision-deficiency separation on a white surface; colours
below 3:1 contrast are always used with direct labels or a second encoding (marker shape, line style, hatching)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK = "#0b0b0b"; INK2 = "#52514e"; MUTED = "#898781"; GRID = "#e1e0d9"; AXIS = "#c3c2b7"; NEUTRAL = "#d9d8d2"

# study accents (high engagement first)
S01 = {"high": "#2a78d6", "low": "#eb6834"}                       # blue / orange
S02 = {"valid": "#1baf7a", "outside": "#6250d6", "none": "#eda100"}  # aqua / violet / yellow (checkup availability)
S02_ITEM = "#6250d6"
S03 = {"high": "#008300", "low": "#e87ba4"}                       # green / magenta
SEQ_GREEN = ["#f3f8f1", "#d8ecd3", "#b3dbaa", "#83c477", "#4fa646", "#1f8424", "#006300", "#004a00"]


def use():
	plt.rcParams.update({
		"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"], "font.size": 8.5,
		"axes.edgecolor": AXIS, "axes.labelcolor": INK, "axes.titlesize": 9.5, "axes.titleweight": "bold", "axes.titlecolor": INK,
		"axes.spines.top": False, "axes.spines.right": False, "axes.linewidth": 0.8, "axes.grid": False,
		"xtick.color": INK2, "ytick.color": INK2, "xtick.major.size": 3, "ytick.major.size": 3, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
		"legend.frameon": False, "legend.fontsize": 7.5, "savefig.dpi": 300, "savefig.bbox": "tight", "figure.dpi": 100,
		"lines.linewidth": 1.6, "patch.linewidth": 0,
	})


def panel(ax, letter, title=None):
	"""Bold panel letter at the top left, optional short title after it."""
	ax.set_title(f"{letter}  {title}" if title else letter, loc="left", pad=6)


def hgrid(ax):
	ax.yaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)


def vgrid(ax):
	ax.xaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
