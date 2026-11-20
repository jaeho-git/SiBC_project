// Markdown -> docx in the SiBC report format (matches SiBC_식이분석_섭취활동_시간정렬_문헌조사보고서_20261022.docx):
// Pretendard, A4 1134 margins, navy H1 (0A3D9A), bold H2, navy table headers with white text, alternating
// F8FAFC rows, E5E7EB borders, callout box F1F5FF for blockquotes, centered gray footer with page number.
// Usage: node md_to_docx_report.js <in.md> <out.docx> "<category>" "<title>" "<abstract>"
const fs = require("fs");
const {
	Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType,
	AlignmentType, BorderStyle, LevelFormat, Footer, PageNumber,
} = require("docx");

const [, , IN, OUT, CATEGORY, TITLE, ABSTRACT] = process.argv;
if (!IN || !OUT) { console.error("usage: node md_to_docx_report.js in.md out.docx category title abstract"); process.exit(1); }
const md = fs.readFileSync(IN, "utf8").split("\n");

const FONT = "Pretendard", MONO = "Menlo";
const NAVY = "0A3D9A", BLUE = "0A64FC", RED = "D92D20", GRAY = "6B7280", LINE = "E5E7EB", ALT = "F8FAFC", CALLOUT = "F1F5FF", CODEBG = "F8FAFC";
const PAGE_W = 11906, MARGIN = 1134, CONTENT_W = 9638;
const LINE_SP = 293;
const border = (color = LINE) => ({ style: BorderStyle.SINGLE, size: 4, color });
const borders = (color = LINE) => ({ top: border(color), bottom: border(color), left: border(color), right: border(color) });

function runs(text, base = {}) {
	const out = [];
	const s = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1");
	const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
	let last = 0, m;
	const size = base.size || 20;
	while ((m = re.exec(s)) !== null) {
		if (m.index > last) out.push(new TextRun({ text: s.slice(last, m.index), font: FONT, ...base, size }));
		const tok = m[0];
		if (tok.startsWith("**")) out.push(new TextRun({ text: tok.slice(2, -2), font: FONT, ...base, size, bold: true }));
		else out.push(new TextRun({ text: tok.slice(1, -1), font: MONO, ...base, size: size - 2 }));
		last = m.index + tok.length;
	}
	if (last < s.length) out.push(new TextRun({ text: s.slice(last), font: FONT, ...base, size }));
	return out;
}
const body = (text, extra = {}) => new Paragraph({ children: runs(text), spacing: { after: 100, line: LINE_SP }, ...extra });

function heading(text, level) {
	if (level === 1) return new Paragraph({ heading: HeadingLevel.HEADING_1, keepNext: true, children: runs(text.replace(/\*\*/g, ""), { size: 28, bold: true, color: NAVY }), spacing: { before: 180, after: 180, line: LINE_SP } });
	if (level === 2) return new Paragraph({ heading: HeadingLevel.HEADING_2, keepNext: true, children: runs(text.replace(/\*\*/g, ""), { size: 23, bold: true }), spacing: { before: 140, after: 100, line: LINE_SP } });
	return new Paragraph({ heading: HeadingLevel.HEADING_3, keepNext: true, children: runs(text.replace(/\*\*/g, ""), { size: 21, bold: true, color: "1F4D78" }), spacing: { before: 120, after: 80, line: LINE_SP } });
}

function boxTable(paragraphs, fill) {
	return new Table({
		width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W],
		rows: [new TableRow({ children: [new TableCell({
			width: { size: CONTENT_W, type: WidthType.DXA }, borders: borders(), shading: { type: ShadingType.CLEAR, fill },
			margins: { top: 70, bottom: 70, left: 100, right: 100 }, children: paragraphs,
		})] })],
	});
}
const callout = text => boxTable([new Paragraph({ children: runs(text), spacing: { line: 264 } })], CALLOUT);
const codeBlock = lines => boxTable(lines.map(l => new Paragraph({ children: [new TextRun({ text: l.length ? l : " ", font: MONO, size: 15 })], spacing: { after: 0, line: 240 } })), CODEBG);
const gap = (after = 120) => new Paragraph({ spacing: { after } });

function splitRow(line) {
	const cells = []; let cur = "", esc = false;
	for (const ch of line.trim().replace(/^\|/, "").replace(/\|$/, "")) {
		if (ch === "\\") { esc = true; continue; }
		if (ch === "|" && !esc) { cells.push(cur.trim()); cur = ""; } else cur += ch;
		esc = false;
	}
	cells.push(cur.trim()); return cells;
}

function table(rows) {
	const header = splitRow(rows[0]); const data = rows.slice(2).map(splitRow); const n = header.length;
	const lens = header.map((h, i) => Math.max(h.length, ...data.map(r => (r[i] || "").length)));
	const w = lens.map(l => Math.sqrt(Math.min(l, 120) + 4));
	const total = w.reduce((a, b) => a + b, 0);
	const widths = w.map(x => Math.round(CONTENT_W * x / total));
	widths[n - 1] += CONTENT_W - widths.reduce((a, b) => a + b, 0);
	const cell = (text, i, kind) => new TableCell({
		width: { size: widths[i], type: WidthType.DXA }, borders: borders(),
		shading: { type: ShadingType.CLEAR, fill: kind === "head" ? NAVY : kind === "alt" ? ALT : "FFFFFF" },
		margins: { top: 70, bottom: 70, left: 100, right: 100 },
		children: [new Paragraph({ children: runs(text, kind === "head" ? { size: 18, bold: true, color: "FFFFFF" } : { size: 18 }), spacing: { after: 0, line: 264 } })],
	});
	return new Table({
		width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths, layout: "fixed",
		rows: [
			new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, i, "head")) }),
			...data.map((r, k) => new TableRow({ cantSplit: true, children: header.map((_, i) => cell(r[i] || "", i, k % 2 === 0 ? "alt" : "plain")) })),
		],
	});
}

// ---------- parse
const children = [];
let i = 0, inCode = false, code = [], tbl = [], titleSeen = false;
let listNo = -1, prevWasNumber = false;   // each numbered list restarts at 1 via its own numbering instance
const flushTable = () => { if (tbl.length) { children.push(table(tbl)); children.push(gap(160)); tbl = []; } };
while (i < md.length) {
	const line = md[i];
	if (line.startsWith("```")) {
		if (inCode) { children.push(codeBlock(code)); children.push(gap()); code = []; inCode = false; } else { flushTable(); inCode = true; }
		i++; continue;
	}
	if (inCode) { code.push(line); i++; continue; }
	if (line.startsWith("|")) { tbl.push(line); i++; continue; }
	flushTable();
	if (line.trim() === "---") { i++; continue; }
	const h = line.match(/^(#{1,3})\s+(.*)$/);
	if (h) {
		if (h[1].length === 1) { titleSeen = true; i++; while (i < md.length && !/^##\s/.test(md[i])) i++; continue; } // skip md title + preamble (handled by title block)
		children.push(heading(h[2], h[1].length - 1 === 0 ? 1 : h[1].length - 1 === 1 ? 2 : 3));
		i++; continue;
	}
	const bullet = line.match(/^\s*[-*]\s+(.*)$/);
	if (bullet) { children.push(new Paragraph({ children: runs(bullet[1]), numbering: { reference: "bullets", level: 0 }, spacing: { after: 60, line: LINE_SP } })); i++; continue; }
	const num = line.match(/^\s*(\d+)\.\s+(.*)$/);
	if (num) {
		// a list restarts when the markdown number is 1 (or on the first item); items after an interleaved
		// code block / paragraph keep the running instance so "1. … ```…``` 2. …" stays one list
		if (parseInt(num[1], 10) === 1 || listNo < 0) listNo++;
		prevWasNumber = true;
		children.push(new Paragraph({ children: runs(num[2]), numbering: { reference: `numbers${Math.min(listNo, 39)}`, level: 0 }, spacing: { after: 60, line: LINE_SP } }));
		i++; continue;
	}
	prevWasNumber = false;
	const quote = line.match(/^>\s?(.*)$/);
	if (quote) { let t = quote[1]; while (i + 1 < md.length && /^>/.test(md[i + 1])) { i++; t += " " + md[i].replace(/^>\s?/, ""); } children.push(callout(t)); children.push(gap()); i++; continue; }
	if (line.trim() === "") { i++; continue; }
	let text = line;
	while (i + 1 < md.length && md[i + 1].trim() !== "" && !/^(#|\||```|\s*[-*]\s|\s*\d+\.\s|>|---)/.test(md[i + 1])) { i++; text += " " + md[i].trim(); }
	children.push(body(text));
	i++;
}
flushTable();

const front = [
	new Paragraph({ children: [new TextRun({ text: "헬스커넥트(주) · AI플랫폼본부 SiBC", bold: true, size: 20, font: FONT })], spacing: { after: 60, line: LINE_SP } }),
	new Paragraph({ children: [new TextRun({ text: "대외비 · CONFIDENTIAL", bold: true, size: 17, font: FONT, color: RED })], spacing: { after: 240, line: LINE_SP } }),
	new Paragraph({ children: [new TextRun({ text: CATEGORY, bold: true, size: 20, font: FONT, color: BLUE })], spacing: { after: 100, line: LINE_SP } }),
	new Paragraph({ keepNext: true, children: [new TextRun({ text: TITLE, bold: true, size: 44, font: FONT })], spacing: { after: 160, line: LINE_SP } }),
	new Paragraph({ children: [new TextRun({ text: "오재호 과장  |  AI플랫폼본부 SiBC", size: 19, font: FONT, color: GRAY })], spacing: { after: 80, line: LINE_SP } }),
	new Paragraph({ children: [new TextRun({ text: ABSTRACT, size: 19, font: FONT, color: GRAY })], spacing: { after: 180, line: LINE_SP } }),
];

const doc = new Document({
	styles: {
		default: { document: { run: { font: FONT, size: 20 } } },
		paragraphStyles: [
			{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, color: NAVY, font: FONT }, paragraph: { spacing: { before: 180, after: 180, line: LINE_SP }, outlineLevel: 0 } },
			{ id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 23, bold: true, font: FONT }, paragraph: { spacing: { before: 140, after: 100, line: LINE_SP }, outlineLevel: 1 } },
			{ id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 21, bold: true, color: "1F4D78", font: FONT }, paragraph: { spacing: { before: 120, after: 80, line: LINE_SP }, outlineLevel: 2 } },
		],
	},
	numbering: { config: [
		{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] },
		...Array.from({ length: 40 }, (_, k) => ({ reference: `numbers${k}`, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } }] })),
	] },
	sections: [{
		properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN, header: 708, footer: 708 } } },
		footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [
			new TextRun({ text: `${TITLE} · 헬스커넥트(주) · 대외비   `, size: 16, font: FONT, color: GRAY }),
			new TextRun({ children: [PageNumber.CURRENT], size: 16, font: FONT, color: GRAY }),
		] })] }) },
		children: [...front, ...children],
	}],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, buf.length, "bytes"); });
