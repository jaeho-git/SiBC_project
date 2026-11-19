// Markdown (GFM subset) -> DOCX, styled after 초기서비스_추세판정_방법비교_분석_20261105.docx
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType,
  BorderStyle, ShadingType, AlignmentType, HeadingLevel, LevelFormat,
  ExternalHyperlink, TableLayoutType,
} = require("docx");

const [,, src, out] = process.argv;
const md = fs.readFileSync(src, "utf8").split(/\r?\n/);

// ---- reference palette / metrics (measured from the reference docx) ----
const FONT = "Pretendard";
const runFont = { ascii: FONT, hAnsi: FONT, eastAsia: FONT, cs: FONT };
const C_NAVY = "0A3D9A", C_INK = "111827", C_GRAY = "6B7280", C_RED = "D92D20", C_BLUE = "0A64FC", C_BAND = "F8FAFC";
const BODY = 21;        // 10.5pt default
const TBL = 20;         // 10pt in tables (reference)
const TBL_WIDE = 18;    // 9pt for 5+ column tables
const PAGE = { width: 11906, height: 16838 };
const MARGIN = { top: 1300, bottom: 1300, left: 1440, right: 1440, header: 708, footer: 708 };
const TABLE_W = 9026;

// ---- front matter (reference layout: org / confidential / eyebrow / title / author / abstract) ----
// Front-matter text (organisation, author, title...) is passed as a local JSON file (4th argument) that is never
// committed; the defaults below are neutral placeholders.
const FRONT = process.argv[4] ? JSON.parse(fs.readFileSync(process.argv[4], "utf8")) : {
  org: "",
  confidential: "",
  eyebrow: "",
  title: "",
  author: "",
  abstract: "",
};

// ---------- inline parsing ----------
function inline(text, o = {}) {
  const size = o.size || BODY;
  const base = { font: runFont, size, color: o.color, bold: o.bold, italics: o.italics };
  const runs = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  let last = 0, m;
  const push = (t, extra = {}) => { if (t) runs.push(new TextRun({ ...base, ...extra, text: t })); };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) push(tok.slice(2, -2), { bold: true });
    else if (tok.startsWith("`")) push(tok.slice(1, -1), { font: { ascii: "Menlo", hAnsi: "Menlo", eastAsia: FONT }, size: size - 2 });
    else {
      const mm = tok.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      runs.push(new ExternalHyperlink({ link: mm[2], children: [new TextRun({ ...base, text: mm[1], style: "Hyperlink" })] }));
    }
    last = m.index + tok.length;
  }
  push(text.slice(last));
  return runs;
}

// ---------- block parsing ----------
const blocks = [];
let i = 0;
// skip H1 + meta lines up to first hr (replaced by FRONT)
let sawH1 = false;
while (i < md.length) {
  const line = md[i];
  if (/^\s*$/.test(line)) { i++; continue; }
  if (!sawH1 && /^#\s/.test(line)) { sawH1 = true; i++; continue; }
  if (sawH1 && blocks.length === 0 && /^[^#>|\-*\d].*:\s/.test(line) && !/^---/.test(line)) { i++; continue; } // meta "key: value" lines
  if (/^---+\s*$/.test(line)) { blocks.push({ type: "hr" }); i++; continue; }
  let h;
  if ((h = line.match(/^(#{1,4})\s+(.*)$/))) { blocks.push({ type: "h", level: h[1].length, text: h[2] }); i++; continue; }
  if (line.startsWith("|")) {
    const rows = [];
    while (i < md.length && md[i].startsWith("|")) { rows.push(md[i]); i++; }
    const cells = rows.map(r => r.replace(/^\|/, "").replace(/\|\s*$/, "").split("|").map(c => c.trim()));
    blocks.push({ type: "table", header: cells[0], body: cells.slice(1).filter(r => !r.every(c => /^:?-{2,}:?$/.test(c))) });
    continue;
  }
  if (line.startsWith(">")) {
    const ls = [];
    while (i < md.length && md[i].startsWith(">")) { ls.push(md[i].replace(/^>\s?/, "")); i++; }
    blocks.push({ type: "quote", lines: ls });
    continue;
  }
  if (/^\s*[-*]\s+/.test(line)) {
    const items = [];
    while (i < md.length && /^\s*[-*]\s+/.test(md[i])) {
      const indent = md[i].match(/^(\s*)/)[1].length;
      items.push({ text: md[i].replace(/^\s*[-*]\s+/, ""), level: indent >= 2 ? 1 : 0 }); i++;
    }
    blocks.push({ type: "ul", items }); continue;
  }
  if (/^\s*\d+\.\s+/.test(line)) {
    const items = [];
    while (i < md.length && /^\s*\d+\.\s+/.test(md[i])) {
      const mm = md[i].match(/^\s*(\d+)\.\s+(.*)$/);
      items.push({ num: mm[1], text: mm[2] }); i++;
    }
    blocks.push({ type: "ol", items }); continue;
  }
  blocks.push({ type: "p", text: line }); i++;
}

// ---------- rendering ----------
const bd = { style: BorderStyle.SINGLE, size: 4, color: "auto" };
const borders = { top: bd, bottom: bd, left: bd, right: bd, insideHorizontal: bd, insideVertical: bd };
const cellMargins = { top: 55, bottom: 55, left: 100, right: 100 };

function makeTable(block) {
  const ncol = block.header.length;
  const size = (ncol >= 5 || block.body.length > 20) ? TBL_WIDE : TBL;
  const rows = [block.header, ...block.body.map(r => { const c = r.slice(0, ncol); while (c.length < ncol) c.push(""); return c; })];
  const lens = Array(ncol).fill(0);
  rows.forEach(r => r.forEach((c, k) => {
    const plain = c.replace(/\*\*|`/g, "").replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
    let l = 0; for (const ch of plain) l += /[ᄀ-ᇿ㄰-㆏가-힯一-鿿]/.test(ch) ? 2 : 1;
    lens[k] = Math.max(lens[k], Math.min(l, 80));
  }));
  const minw = 1000;
  const raw = lens.map(l => Math.max(l, 8));
  const sum = raw.reduce((a, b) => a + b, 0);
  // short columns (numbers, PMIDs) get enough room to stay on one line
  const need = lens.map(l => l <= 16 ? Math.round(l * (size / 2) * 0.58 * 20) + 230 : minw);
  let widths = raw.map((l, k) => Math.max(minw, need[k], Math.round(TABLE_W * l / sum)));
  const s2 = widths.reduce((a, b) => a + b, 0);
  widths = widths.map(w => Math.round(w * TABLE_W / s2));
  widths[ncol - 1] += TABLE_W - widths.reduce((a, b) => a + b, 0);

  const mkCell = (text, k, ri) => {
    const isHeader = ri === 0;
    const fill = isHeader ? C_NAVY : (ri % 2 === 1 ? "FFFFFF" : C_BAND);
    return new TableCell({
      width: { size: widths[k], type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill, color: "auto" },
      margins: cellMargins,
      children: [new Paragraph({ children: inline(text, { size, bold: isHeader || undefined, color: isHeader ? "FFFFFF" : C_INK }) })],
    });
  };
  return new Table({
    width: { size: TABLE_W, type: WidthType.DXA },
    columnWidths: widths,
    layout: TableLayoutType.FIXED,
    borders,
    rows: rows.map((r, ri) => new TableRow({ tableHeader: ri === 0, cantSplit: true, children: r.map((c, k) => mkCell(c, k, ri)) })),
  });
}

const NOTE_RE = /^(참고[:：]|※)/;
const LEAD_RE = /^(참고|읽는 법|전제|원칙)[:：]\s+/; // "해석: ..." -> bold navy lead-in

function para(text, o = {}) {
  const m = o.lead !== false && text.match(LEAD_RE);
  if (m && !/\*\*/.test(m[1])) {
    return new Paragraph({ spacing: { after: o.after ?? 120 }, children: [
      new TextRun({ text: m[1] + ": ", font: runFont, size: o.size || BODY, bold: true, color: C_NAVY }),
      ...inline(text.slice(m[0].length), { size: o.size, color: o.color }),
    ] });
  }
  return new Paragraph({ spacing: { after: o.after ?? 120 }, children: inline(text, { size: o.size, color: o.color, bold: o.bold }) });
}

function renderBlock(b, prev) {
  switch (b.type) {
    case "h": {
      if (b.level === 2) return [new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 340, after: 140 }, children: inline(b.text) })];
      if (b.level === 3) return [new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 110 }, children: inline(b.text) })];
      return [new Paragraph({ spacing: { before: 200, after: 90 }, children: inline(b.text, { bold: true, color: C_INK }) })];
    }
    case "hr": return [];
    case "p": {
      if (/^\*\*[^*]+\*\*$/.test(b.text.trim())) // bold-only line = sub-heading
        return [new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 110 }, children: inline(b.text.replace(/\*\*/g, "")) })];
      const afterTable = prev && prev.type === "table";
      if (NOTE_RE.test(b.text)) return [para(b.text, { size: 20, color: C_GRAY })];
      return [para(b.text)];
    }
    case "quote": {
      const outp = [];
      b.lines.forEach((l, k) => {
        if (k === 0 && !/^[-*]\s/.test(l)) outp.push(new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: l, font: runFont, size: 20, bold: true, color: C_NAVY })] }));
        else outp.push(new Paragraph({ spacing: { after: 60 }, indent: { left: 240 }, children: inline(l.replace(/^[-*]\s+/, "· "), { size: 20, color: C_GRAY }) }));
      });
      outp.push(new Paragraph({ spacing: { after: 90 }, children: [] }));
      return outp;
    }
    case "ul": return b.items.map(it => new Paragraph({ numbering: { reference: "bullets", level: it.level }, spacing: { after: 70 }, children: inline(it.text) }));
    case "ol": return b.items.map(it => new Paragraph({
      spacing: { after: 90 }, indent: { left: 420, hanging: 420 },
      children: [new TextRun({ text: it.num + ".\t", font: runFont, size: BODY, bold: true, color: C_NAVY }), ...inline(it.text)],
    }));
    case "table": return [makeTable(b), new Paragraph({ spacing: { after: 90 }, children: [] })];
  }
  return [];
}

// ---------- front matter ----------
const children = [
  new Paragraph({ spacing: { after: 40 }, children: [new TextRun({ text: FRONT.org, font: runFont, size: 20, bold: true, color: C_GRAY })] }),
  new Paragraph({ spacing: { after: 160 }, children: [new TextRun({ text: FRONT.confidential, font: runFont, size: 17, bold: true, color: C_RED })] }),
  new Paragraph({ spacing: { after: 60 }, children: [new TextRun({ text: FRONT.eyebrow, font: runFont, size: 20, bold: true, color: C_BLUE })] }),
  new Paragraph({ heading: HeadingLevel.TITLE, spacing: { after: 80 }, children: [new TextRun({ text: FRONT.title, font: runFont })] }),
  new Paragraph({ spacing: { after: 50 }, children: [new TextRun({ text: FRONT.author, font: runFont, size: 19, color: C_GRAY })] }),
  new Paragraph({ spacing: { after: 220 }, children: [new TextRun({ text: FRONT.abstract, font: runFont, size: 19, color: C_GRAY })] }),
];
let prev = null;
for (const b of blocks) { children.push(...renderBlock(b, prev)); if (b.type !== "hr") prev = b; }
// a document ending in a table: shrink the trailing spacer so it cannot spill onto a blank page
if (prev && prev.type === "table") {
  children.pop();
  children.push(new Paragraph({ spacing: { before: 0, after: 0, line: 20, lineRule: "exact" }, children: [new TextRun({ text: "", size: 2 })] }));
}

const doc = new Document({
  creator: "AI플랫폼본부 SiBC",
  title: FRONT.title,
  styles: {
    default: { document: { run: { font: runFont, size: BODY, language: { value: "en-KR", eastAsia: "ko-KR" } } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: runFont, size: 46, bold: true, color: C_INK }, paragraph: { spacing: { before: 0, after: 80 }, keepNext: true } },
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: runFont, size: 28, bold: true, color: C_NAVY }, paragraph: { spacing: { before: 340, after: 140 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: runFont, size: 23, bold: true, color: C_INK }, paragraph: { spacing: { before: 240, after: 110 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: runFont, size: 21, bold: true, color: C_INK }, paragraph: { spacing: { before: 200, after: 90 }, keepNext: true, outlineLevel: 2 } },
    ],
    characterStyles: [{ id: "Hyperlink", name: "Hyperlink", run: { color: "0563C1", underline: {} } }],
  },
  numbering: { config: [{ reference: "bullets", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 420, hanging: 220 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 840, hanging: 220 } } } },
  ] }] },
  sections: [{ properties: { page: { size: PAGE, margin: MARGIN } }, children }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(out, buf); console.log("wrote", out, buf.length, "bytes;", blocks.filter(b => b.type === "table").length, "tables"); });
