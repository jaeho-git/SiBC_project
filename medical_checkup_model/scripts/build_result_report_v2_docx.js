// 결과 보고서 v2(가이드라인 판정 기준 + 근거 부록 포함). 원본 주석: 결과 보고서(첫 보고용): 과거 데이터셋·이전 모델과의 비교 없이 '최신 데이터셋으로 만든 모델의 결과와 제한' 중심. 원본 주석: 고도화 결과 보고서 v2 — 경영진 보고용 간결판(2쪽 핵심 요약 + 본문 6장). 헬퍼는 v1과 동일 — 원본 주석: 모델 분석 보고서 v3 — v2(푸드렌즈 템플릿 포맷)에서 (1) 표 테두리를 표 단위로 통일(뷰어별 선 어긋남 방지), (2) '봉인' 등 전문 용어를 쉬운 말로 교체,
// (3) 보고서 구성표·장별 요점·그림 번호(1~6) 상호참조를 추가해 추적성을 높임. 실행: NODE_PATH=<docx 위치> node scripts/build_analysis_report_v3_docx.js
const fs = require("fs"), path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel, LevelFormat, ImageRun, Footer, PageNumber, TabStopType, VerticalAlign, TableLayoutType } = require("docx");
const ROOT = path.join(__dirname, ".."), ASSETS = path.join(__dirname, "result_assets");
const J = f => JSON.parse(fs.readFileSync(path.join(ROOT, f), "utf8").replace(/\bNaN\b/g, "null"));
const audit = J("01_Results/model_audit.json"), m2 = J("01_Results/m2/m2_report.json"), ds = J("01_Results/data_status_2026-09-17.json"), up = J("01_Results/m2/upgrade_summary.json");
const sig = J("01_Results/significance.json");
const C = { navy: "0A3D9A", blue: "0A64FC", gray: "6B7280", text: "111827", red: "D92D20", line: "D1D5DB", zebra: "F8FAFC", amber: "FEF3C7", pale: "F1F5FF", green: "15803D", rose: "FDECEA", mint: "E8F5E9" };
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, LINE = { style: BorderStyle.SINGLE, size: 4, color: C.line };
const TW = 9638; // 본문 폭(twip)
const ch = [];
const R = (t, o = {}) => new TextRun({ text: t, bold: !!o.bold, color: o.color, size: o.size });
const P = (runs, o = {}) => new Paragraph({ spacing: Object.assign({ after: 110, line: 295, lineRule: "auto" }, o.spacing || {}), keepNext: o.keepNext, pageBreakBefore: o.pageBreakBefore, alignment: o.align, children: runs });
const body = (t, o) => ch.push(P(typeof t === "string" ? [R(t)] : t, o));
const partHead = (label, title, sub) => { ch.push(P([R(label, { bold: true, color: C.blue, size: 24 })], { spacing: { before: 100, after: 80 }, pageBreakBefore: true })); ch.push(P([R(title, { bold: true, size: 32 })], { spacing: { after: 120 } })); ch.push(P([R(sub, { color: C.gray, size: 22 })], { spacing: { after: 200 } })); };
const h1 = (t, pb = false) => ch.push(new Paragraph({ heading: HeadingLevel.HEADING_1, keepNext: true, pageBreakBefore: pb, spacing: { before: pb ? 0 : 320, after: 120 }, children: [R(t, { bold: true, color: C.navy, size: 28 })] }));
// 장 요점: 각 장 첫머리에 '이 장에서 확인할 것'을 한 줄로
const point = t => ch.push(new Paragraph({ keepNext: true, spacing: { after: 140, line: 280, lineRule: "auto" }, border: { left: { style: BorderStyle.SINGLE, size: 12, color: C.blue, space: 8 } }, indent: { left: 120 }, children: [R("요점  ", { bold: true, color: C.blue, size: 19 }), R(t, { color: C.navy, size: 19 })] }));
const bullet = (lead, t) => ch.push(new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 65, line: 280, lineRule: "auto" }, children: lead ? [R(lead + " ", { bold: true }), R(t)] : [R(t)] }));
const src = t => ch.push(P([R("자료: " + t, { color: C.gray, size: 18 })], { spacing: { before: 160 } }));
const TBORDER = { top: LINE, bottom: LINE, left: LINE, right: LINE, insideHorizontal: LINE, insideVertical: LINE };
const NOBORDER = { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE };
function callout(lead, t, fill = C.pale, bar = C.blue, bold = true) {
  ch.push(new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: [TW], layout: TableLayoutType.FIXED,
    borders: { top: NONE, bottom: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE, left: { style: BorderStyle.SINGLE, size: 24, color: bar } },
    margins: { marginUnitType: WidthType.DXA, top: 108, bottom: 108, left: 160, right: 160 },
    rows: [new TableRow({ cantSplit: true, children: [new TableCell({ width: { size: TW, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill },
      children: [new Paragraph({ spacing: { line: 285, lineRule: "auto" }, children: [R(lead, { bold: true, color: bar }), R(t, { bold, color: bar === C.blue ? C.navy : C.text })] })] })] })] }));
}
// 표: 테두리·여백을 표 단위(tblBorders/tblCellMar)로만 지정 → Word·LibreOffice·미리보기에서 셀 선이 어긋나지 않음. 셀은 폭·배경·수직정렬만.
function table(header, rows, widths, opts = {}) {
  const sc = TW / widths.reduce((a, b) => a + b, 0), W = widths.map(w => Math.round(w * sc)); W[W.length - 1] += TW - W.reduce((a, b) => a + b, 0);
  const fs_ = opts.compact ? 17 : 18, vm = opts.compact ? 48 : 80;
  const cell = (t, w, head, fill) => new TableCell({ width: { size: w, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: head ? C.navy : (fill || "FFFFFF") }, verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ spacing: { before: 0, after: 0, line: 250, lineRule: "auto" }, children: [R(String(t), { bold: head, color: head ? "FFFFFF" : C.text, size: fs_ })] })] });
  ch.push(new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: W, layout: TableLayoutType.FIXED, borders: TBORDER,
    margins: { marginUnitType: WidthType.DXA, top: vm, bottom: vm, left: 100, right: 100 },
    rows: [new TableRow({ tableHeader: true, cantSplit: true, children: header.map((t, i) => cell(t, W[i], true)) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((t, i) => cell(t, W[i], false, r.__fill || ((opts.zebra !== false && ri % 2 === 1) ? C.zebra : undefined))) }))] }));
  ch.push(P([], { spacing: { after: 120 } }));
}
const hl = (a, f = C.amber) => { a.__fill = f; return a; };
function figure(no, title, file, caption, w = 643, h = 367) {
  ch.push(P([R(`그림 ${no}. ${title}`, { bold: true, color: C.navy, size: 22 })], { keepNext: true, spacing: { before: 120, after: 60 } }));
  ch.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(ASSETS, file)), transformation: { width: w, height: h } })] }));
  ch.push(P([], { spacing: { after: 140 } }));
}



const yaml = require("js-yaml");
const GL = yaml.load(fs.readFileSync(path.join(ROOT, "configs/clinical_guidelines.yaml"), "utf8"));
const sg = sig.m1, fu = m2.fusion, rf = m2.referral, tp = m2.temporal, nc = m2.noise_ceiling, tv = m2.tier_validation;
const rs = J("01_Results/m2/result_summary.json"), crep = J("01_Results/clinical/clinical_report.json").thresholds;
const wn = ds.wearable_now, bf = wn.by_feature, fn = ds.forward_now, ln = ds.labels_now;
const pct = x => Math.round(x * 100) + "%";
const gain = k => Math.round((1 - sg[k].mae_model / sg[k].mae_cf) * 100);
const room = Math.round((1 - nc.sbp.mae_floor_estimate / sg.sbp.mae_model) * 100);
const S = GL.sources, ref = k => { const s = S[k]; return s.pmid ? `PMID ${s.pmid}` : (s.doi ? `DOI ${s.doi}` : "학회·정부 발간물"); };
const DOM = [["blood_pressure", "혈압"], ["fasting_glucose", "공복혈당"], ["obesity_bmi", "비만(BMI)"], ["abdominal_obesity", "복부비만"]];
const totalRisk = DOM.reduce((a, [k]) => a + tv[k].final.actual_risk_n, 0), totalMiss = DOM.reduce((a, [k]) => a + tv[k].final.actual_risk_missed_as_normal, 0), priorMiss = DOM.reduce((a, [k]) => a + tv[k].prior_status.actual_risk_missed_as_normal, 0);
// 핵심 수치 카드(4칸): 큰 숫자 + 설명
function kpi(cards) {
  const w = Math.floor(TW / cards.length), W = cards.map((_, i) => i === cards.length - 1 ? TW - w * (cards.length - 1) : w);
  ch.push(new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: W, layout: TableLayoutType.FIXED,
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: { style: BorderStyle.SINGLE, size: 12, color: "FFFFFF" } },
    margins: { marginUnitType: WidthType.DXA, top: 140, bottom: 140, left: 140, right: 100 },
    rows: [new TableRow({ cantSplit: true, children: cards.map((c, i) => new TableCell({ width: { size: W[i], type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill: c.fill || C.pale }, verticalAlign: VerticalAlign.TOP,
      children: [new Paragraph({ spacing: { after: 40 }, children: [R(c.label, { bold: true, color: C.gray, size: 17 })] }),
                 new Paragraph({ spacing: { after: 40 }, children: [R(c.value, { bold: true, color: c.color || C.navy, size: 30 })] }),
                 new Paragraph({ spacing: { after: 0, line: 250, lineRule: "auto" }, children: [R(c.note, { color: C.text, size: 17 })] })] })) })] }));
  ch.push(P([], { spacing: { after: 140 } }));
}
const sub = t => ch.push(P([R(t, { bold: true, size: 24 })], { spacing: { before: 220, after: 100 }, keepNext: true }));



// ================= 표지 =================
ch.push(P([R("헬스커넥트(주) · AI플랫폼본부 SiBC", { bold: true, size: 22 })], { spacing: { after: 55 } }));
ch.push(P([R("대외비 · CONFIDENTIAL", { bold: true, color: C.red, size: 18 })], { spacing: { after: 1450 } }));
ch.push(P([R("WEARABLE-BASED HEALTH CHECKUP PREDICTION MODEL", { bold: true, color: C.blue, size: 24 })], { spacing: { after: 210 } }));
ch.push(P([R("건강검진 예측 모델 결과 보고서", { bold: true, size: 52 })], { spacing: { after: 110 } }));
ch.push(P([R("모델 성능 · 임상 가이드라인 기반 판정 기준 · 제한사항", { size: 30 })], { spacing: { after: 5200 } }));
ch.push(P([R("오재호 과장", { bold: true, size: 26 })], { spacing: { after: 55 } }));
ch.push(P([R("AI플랫폼본부 SiBC · 데이터 기준일 2026-09-17 · 가이드라인 확인일 2026-09-18", { color: C.gray })], { spacing: { after: 36 } }));

// ================= 핵심 요약 =================
ch.push(P([R("EXECUTIVE SUMMARY", { bold: true, color: C.blue, size: 24 })], { spacing: { before: 90, after: 80 }, pageBreakBefore: true }));
ch.push(P([R("핵심 요약", { bold: true, size: 32 })], { spacing: { after: 140 } }));
callout("결론  ", `과거 검진 기록과 웨어러블 측정값으로 검진 수치를 추정하고, 그 결과를 국내 학회 진료지침과 국가건강검진 기준에 따라 정상·주의·위험으로 판정하는 모델을 구축했습니다. 검증에서 실제 '위험' 단계였던 ${totalRisk}건 중 '정상'으로 잘못 판정한 경우는 ${totalMiss}건이었습니다. 걸음·심박·수면의 효과는 검증용 데이터가 부족해 아직 확인할 수 없습니다.`);
ch.push(P([], { spacing: { after: 120 } }));
kpi([
  { label: "위험 단계를 '정상'으로 놓친 건수", value: `${totalMiss} / ${totalRisk}건`, note: `혈압·혈당·비만·복부비만 합계. 직전 검진 단계를 그대로 쓰면 ${priorMiss}건`, fill: C.mint, color: C.green },
  { label: "혈압 예측 오차", value: `−${gain("sbp")}% · −${gain("dbp")}%`, note: "직전 검진값 그대로 대비 수축기·이완기. 통계적으로 유의", fill: C.mint, color: C.green },
  { label: "판정 기준의 근거", value: "5개 기관", note: "국내 학회 4곳 진료지침 + 국가검진 고시. 출처·PMID·DOI는 부록" },
  { label: "걸음·심박·수면 검증 데이터", value: `${fn.users_ge1d} / 30명`, note: "'착용 뒤 검진' 기록. 기준 미달로 검증 불가", fill: C.rose, color: C.red },
]);
sub("결과 요약");
table(["구분", "결과", "판정"], [
  ["사용 데이터", `웨어러블 ${wn.users}명, 검진 ${ln.users}명(${ln.events.toLocaleString()}건), 공공데이터 약 1만 건(학습 전용). 평가는 자체 데이터로만 수행`, "—"],
  hl(["판정 기준", "9개 항목의 정상·주의·위험 구간을 학회 지침과 국가검진 기준에서 확인해 설정. 기저질환별 조절 목표를 별도 표로 보존", "근거 확보 (의료진 승인 전)"], C.mint),
  hl(["수치 예측", `직전 검진값 대비 오차 −${gain("sbp")}% / −${gain("dbp")}% / −${gain("fasting_glucose")}% (수축기 / 이완기 / 공복혈당)`, "의료진 검토용"], C.mint),
  hl(["3단계 판정", `실제 '위험' ${totalRisk}건 중 '정상' 판정 ${totalMiss}건. '정상' 판정자 중 실제 위험 0%. 다만 혈압은 '주의' 판정이 ${pct(tv.blood_pressure.final.pred_distribution["주의"] / tv.blood_pressure.n)}로 넓음`, "의료진 검토용"], C.mint),
  hl(["웨어러블 측정값 활용", `체중계 측정값으로 체중 오차 ${fu.weight.with_prior_checkup.mae_base}→${fu.weight.with_prior_checkup.mae_fused} kg. 검진 이력 없는 사용자에게 체중·수축기혈압 제공. 혈압계 측정값은 효과 없음`, "체중만 채택"], C.amber),
  ["지질 4종", "반복 검진 기록이 적어 판정 모델을 학습할 수 없음. 예측 수치에 기준만 적용", "참고용"],
  hl(["제한", `걸음·심박·수면의 효과는 검증 데이터 30명 확보 전까지 확인 불가. 기저질환 정보가 구조화돼 있지 않아 현재는 기본 기준만 적용`, "데이터 필요"], C.rose),
], [2300, 5800, 1538], { zebra: false });
sub("결정이 필요한 사항");
bullet("판정 기준표 승인.", "학회 지침 기반 초안입니다. 의료진 검토 후 확정이 필요합니다.");
bullet("기저질환 정보 수집.", "당뇨병·고혈압 등 진단 여부를 문진 항목으로 받아야 질환별 기준을 적용할 수 있습니다.");
bullet("검진 결과 업로드 캠페인.", "'착용 뒤 검진' 30명 확보가 웨어러블 효과 검증의 유일한 경로입니다. 3~6개월이 걸립니다.");

// ================= 본문 =================
h1("1. 모델 개요와 사용 데이터", true);
table(["구분", "내용"], [
  ["예측 대상", "혈압(수축기·이완기), 공복혈당, 체중·BMI·허리둘레, 지질 4종"],
  ["입력", "과거 검진값과 경과일·추세, 성별·연령, 웨어러블 혈압계·체중계 측정값"],
  ["출력", "예측값과 85% 구간, 정상·주의·위험 판정, 학회 기준 세부 단계(예: 고혈압전단계), 근거가 부족하면 '보류'와 사유"],
  ["학습 데이터", `자체 검진 ${ln.events.toLocaleString()}건(${ln.users}명) + 공공데이터(미국 NHANES 9,981건, 한국 KNHANES 592건). 공공데이터는 학습에만 사용`],
  ["검증 방법", "학습에 쓰지 않은 사용자 61명으로 1회 평가. 비교 기준은 '직전 검진값(단계) 그대로'"],
], [1900, 7738], { compact: true });
body(`그림 1의 왼쪽은 데이터 종류별 사용자 수입니다. 웨어러블 사용자 ${wn.users}명 가운데 혈압계 측정 ${bf.bp_systolic_measured.users}명, 체중계 측정 ${bf.body_weight_measured.users}명이 가장 많고, 검진 기록 보유자는 ${ln.users}명입니다. 오른쪽은 걸음·심박·수면의 효과를 검증하는 데 필요한 '웨어러블 착용 뒤에 받은 검진' 기록으로, 현재 ${fn.users_ge1d}명이어서 검증 시작 기준인 30명에 미치지 못합니다. 걸음·심박·수면 기록 자체는 ${bf.step_count.users}명·${bf.heartrate_median.users}명·${bf.sleep_duration_min.users}명에게 쌓여 있지만 검진값과의 관계를 배울 예시가 부족해, 이번 모델에는 검진값과 직접 대응되는 혈압계·체중계 측정값만 반영했습니다.`);
figure(1, "보유 데이터와 검증 데이터 부족", "R1_data.png", "", 470, 268);

h1("2. 판정 기준 — 임상 가이드라인 기반", true);
table(["항목", "정상", "주의", "위험", "근거"], [
  ["수축기혈압 (mmHg)", "120 미만", "120~139", "140 이상", "대한고혈압학회 2026, 국가검진"],
  ["이완기혈압 (mmHg)", "80 미만", "80~89", "90 이상", "대한고혈압학회 2026, 국가검진"],
  ["공복혈당 (mg/dL)", "100 미만", "100~125", "126 이상", "대한당뇨병학회 2025, 국가검진"],
  hl(["BMI (kg/m²)", "23 미만", "23~24.9", "25 이상", "대한비만학회 2022 (국가검진은 25 / 30)"], C.amber),
  ["허리둘레 (cm)", "남 90 · 여 85 미만", "—", "남 90 · 여 85 이상", "대한비만학회 2022, 국가검진"],
  ["총콜레스테롤 (mg/dL)", "200 미만", "200~239", "240 이상", "한국지질동맥경화학회 2022, 국가검진"],
  ["LDL 콜레스테롤 (mg/dL)", "130 미만", "130~159", "160 이상", "한국지질동맥경화학회 2022, 국가검진"],
  ["중성지방 (mg/dL)", "150 미만", "150~199", "200 이상", "한국지질동맥경화학회 2022, 국가검진"],
  ["HDL 콜레스테롤 (mg/dL)", "60 이상", "40~59", "40 미만", "한국지질동맥경화학회 2022, 국가검진"],
], [2300, 1700, 1400, 1700, 2538], { zebra: false, compact: true });
body("출처 간 경계가 다른 항목은 BMI뿐입니다(학회 25, 국가검진 30). 더 이른 경계인 학회 기준을 적용하고 두 단계명을 모두 산출합니다.");
sub("기저질환별 조절 목표 (질환이 확인된 사용자에게 적용)");
table(["기저질환", "혈압 목표", "LDL 목표", "공복혈당 목표", "근거"], [
  ["당뇨병", "130/80 미만 (이전 지침: 저위험 140/90 미만)", "100 미만 · 고위험 70 미만 · 심혈관질환 동반 55 미만", "80~130", "당뇨병학회 2025, 고혈압학회 2026, 지질동맥경화학회 2022"],
  ["고혈압 (치료 중)", "140/90 미만 · 고위험 130/80 미만", "—", "—", "고혈압학회 2026·2022"],
  ["심혈관질환", "130/80 미만", "관상동맥질환 55 미만 · 그 외 죽상경화성 질환 70 미만", "—", "고혈압학회 2026, 지질동맥경화학회 2022"],
  ["만성콩팥병", "130/80 미만 (2022 지침: 알부민뇨 없으면 140/90 미만)", "—", "—", "고혈압학회 2026·2022"],
  ["뇌졸중", "130/80 미만", "—", "—", "고혈압학회 2026"],
  ["이상지질혈증 (일차 예방)", "—", "위험인자 2개 이상 130 미만 · 1개 이하 160 미만", "—", "지질동맥경화학회 2022"],
], [1700, 2500, 2500, 1100, 1838], { compact: true });
body("지침·개정 연도에 따라 목표가 다르면 합치지 않고 모두 보존하며, 가장 엄격한 목표를 기본 적용합니다. 현재 DB에 진단명 항목이 없어 이번 산출은 전원 기본 기준으로 판정했습니다.");

h1("3. 수치 예측 성능", true);
table(["항목", "오차: 직전값 → 모델", "개선", "시간 순서 검증", "판정"], [
  ["수축기혈압", `${sg.sbp.mae_cf} → ${sg.sbp.mae_model} mmHg`, `−${gain("sbp")}%, 유의`, `−${tp.sbp.improve_pct}%, 통과`, "채택"],
  ["이완기혈압", `${sg.dbp.mae_cf} → ${sg.dbp.mae_model} mmHg`, `−${gain("dbp")}%, 유의`, `−${tp.dbp.improve_pct}%, 통과`, "채택"],
  ["공복혈당", `${sg.fasting_glucose.mae_cf} → ${sg.fasting_glucose.mae_model} mg/dL`, `−${gain("fasting_glucose")}%, 유의`, `−${tp.fasting_glucose.improve_pct}%, 경계`, "채택"],
  ["체중 · BMI · 허리둘레", "모델 개선 3% 미달", "—", "—", "직전값 유지"],
  ["지질 4종", "설명력 낮음", "—", "—", "참고용"],
], [2100, 2700, 1700, 1800, 1338], { compact: true });
body(`그림 2는 항목별 평균 오차를 세 가지로 비교합니다. 연한 파랑은 직전 검진값을 그대로 쓴 경우, 진한 파랑은 예측 모델, 회색은 같은 사람의 검진값이 검진마다 자연스럽게 흔들리는 폭에서 추정한 오차의 하한입니다. 혈압은 모델이 직전값보다 ${gain("sbp")}%·${gain("dbp")}% 정확하며, 하한까지 남은 여지는 약 ${room}%입니다. 공복혈당은 하한 추정에 실제 변화가 섞여 모델보다 높게 나왔습니다.`);
figure(2, "수치 예측 정확도", "R2_accuracy.png", "", 470, 268);
body(`웨어러블 측정값은 체중에서만 효과가 있었습니다. 체중계 측정값을 더하면 체중 오차가 ${fu.weight.with_prior_checkup.mae_base}→${fu.weight.with_prior_checkup.mae_fused} kg으로 줄고(조건부 채택), 검진 이력이 없는 사용자에게도 체중(오차 ${fu.weight.no_prior_checkup.mae_m0_measured} kg)과 참고용 수축기혈압을 제공합니다. 혈압계 측정값은 측정 횟수가 적고(중앙 3회) 조건이 표준화돼 있지 않아 정확도를 높이지 못했습니다.`);

h1("4. 가이드라인 3단계 판정 성능");
body("예측 수치는 실제 고위험자의 값을 낮게 보는 경향(평균 회귀)이 있어, 수치만으로 판정하면 위험군을 놓칩니다. 그래서 판정은 두 가지를 결합합니다. ① 예측값과 85% 구간 상한에 2장의 기준을 적용하고, ② '다음 검진에서 기준을 넘을 확률'을 학습한 판정 모델을 함께 봅니다. 둘 중 더 나쁜 단계를 최종 판정으로 씁니다.");
body(`그림 3은 검증 사용자 가운데 실제로 '위험' 단계였던 검진을 어떻게 판정했는지 보여 줍니다. 항목마다 위 막대는 직전 검진 단계를 그대로 쓴 경우, 아래 막대는 모델 판정이며, 빨강은 '위험', 주황은 '주의', 회색은 '정상'으로 놓친 비율입니다. 직전 단계를 그대로 쓰면 혈압 3명, 복부비만 12명을 '정상'으로 놓치지만 모델 판정은 네 영역 모두 놓침이 0건입니다. 다만 혈압은 실제 위험의 ${pct(tv.blood_pressure.final.actual_risk_called_risk)}만 '위험'으로 바로 판정하고 나머지는 '주의'로 분류합니다.`);
figure(3, "실제 '위험' 단계인 사람을 어떻게 판정했는가", "R6_tier_validation.png", "", 470, 268);
table(["영역", "실제 위험", "'위험' 판정", "'주의' 이상 판정", "'정상'으로 놓침", "'정상' 판정자 중 실제 위험", "'주의' 판정 비율"], [
  ...DOM.map(([k, kor]) => { const v = tv[k], f = v.final; return [kor, `${f.actual_risk_n}건`, pct(f.actual_risk_called_risk), pct(f.actual_risk_called_caution_or_risk), `${f.actual_risk_missed_as_normal}건`, pct(f.pred_normal_actually_risk), pct((f.pred_distribution["주의"] || 0) / v.n)]; }),
], [1500, 1100, 1300, 1600, 1400, 1700, 1038], { compact: true });
callout("유의  ", `놓침을 없앤 대가로 '주의' 판정이 넓습니다. 혈압은 검증 대상의 ${pct(tv.blood_pressure.final.pred_distribution["주의"] / tv.blood_pressure.n)}가 '주의'이고, 실제 위험 ${tv.blood_pressure.final.actual_risk_n}건 중 '위험'으로 바로 판정한 것은 ${pct(tv.blood_pressure.final.actual_risk_called_risk)}입니다. '주의'는 재측정·생활습관 안내, '위험'은 병원 안내로 나누는 운영을 제안합니다.`, C.amber, "D97706", false);
sub("판정 모델 재학습 결과 (가이드라인 경계값 기준)");
body("판별력은 0.5가 동전 던지기, 0.8 이상 양호, 0.9 이상 우수입니다. 8개 문제 모두 '직전 검진 상태 그대로'보다 높았습니다.", { keepNext: true });
table(["판정 문제 (경계값)", "판별력 (AUROC)", "직전 상태 기준선", "상태"], [
  ...[["bp_caution_120_80", "혈압 주의 이상 (120/80)"], ["hypertension_140_90", "혈압 위험 (140/90)"], ["fasting_glucose_ge100", "공복혈당 주의 이상 (100)"], ["fasting_glucose_ge126", "공복혈당 위험 (126)"], ["bmi_ge23", "BMI 주의 이상 (23)"], ["obesity_bmi_ge25", "BMI 위험 (25)"], ["obesity2_bmi_ge30", "2단계 비만 (30)"], ["abdominal_obesity", "복부비만 (남 90 · 여 85)"]]
    .map(([k, n]) => [n, `${crep[k].sealed.auroc}`, `${crep[k].sealed.baseline_prior_status_auroc}`, "채택"]),
  hl(["지질 7개 문제 (총콜레스테롤 200·240, LDL 130·160, 중성지방 150·200, HDL 40)", "—", "—", "학습 보류 (반복 지질 검진 63명)"], C.rose),
], [4800, 1600, 1700, 1538], { compact: true });

h1("5. 전체 사용자 판정 결과와 산출 범위", true);
body(`전체 ${rs.users}명에게 산출했으며, 기저질환 정보가 없어 전원 기본 기준으로 판정했습니다. 그림 4는 항목별 판정 분포로, 초록은 정상, 주황은 주의, 빨강은 위험, 회색은 근거가 부족해 보류한 사용자입니다. 혈압은 '주의'가 ${rs.tier_distribution["혈압"]["주의"]}명으로 가장 많고 '위험'은 ${rs.tier_distribution["혈압"]["위험"]}명입니다. 지질 4종은 판정 모델 없이 예측 수치에 기준만 적용한 참고값입니다.`);
figure(4, "항목별 판정 분포", "R7_tier_distribution.png", "", 520, 297);
table(["항목", "성능 또는 방식", "활용 수준"], [
  hl(["혈압·공복혈당 수치와 3단계 판정", `오차 ${sg.sbp.mae_model} / ${sg.dbp.mae_model} mmHg, ${sg.fasting_glucose.mae_model} mg/dL. 위험 놓침 0건`, "의료진 검토용"], C.mint),
  hl(["비만·복부비만 3단계 판정", `위험을 '위험'으로 판정 ${pct(tv.obesity_bmi.final.actual_risk_called_risk)} / ${pct(tv.abdominal_obesity.final.actual_risk_called_risk)}`, "의료진 검토용"], C.mint),
  hl(["체중·BMI 수치", `체중계 측정값 반영. 오차 ${fu.weight.with_prior_checkup.mae_fused} kg`, "참고 표기"], C.amber),
  hl(["검진 이력 없는 사용자", `체중 오차 ${fu.weight.no_prior_checkup.mae_m0_measured} kg, 수축기 ${fu.sbp.no_prior_checkup.mae_m0_measured} mmHg`, "체중 사용 가능, 혈압 참고"], C.amber),
  ["지질 4종 판정", "예측 수치에 기준만 적용. 판정 모델 없음", "참고용"],
  hl(["걸음·심박·수면을 반영한 예측", `검증 데이터 ${fn.users_ge1d}명 < 30명`, "미검증"], C.rose),
], [3300, 4000, 2338], { zebra: false, compact: true });

h1("6. 제한사항과 보완 계획", true);
table(["제한 (현재 해결 불가)", "이유", "풀리는 조건"], [
  hl(["걸음·심박·수면의 예측 기여 확인", `'착용 뒤 검진' 기록 ${fn.users_ge1d}명. 학습·검증 모두 불가`, "30명 이상 확보 (3~6개월)"], C.rose),
  hl(["기저질환별 기준 적용", "진단명이 구조화된 데이터로 없음 (복약·문진 기록만 존재)", "문진 항목 추가 또는 복약 기록의 질환 매핑"], C.rose),
  ["수치 예측 정확도의 상한", `검진값 자체가 같은 사람도 ±${nc.sbp.sigma_within} mmHg 변동. 남은 여지 약 ${room}%`, "반복 측정으로 기준값의 변동을 줄여야 함"],
  ["지질 판정 모델", "반복 지질 검진 63명. 학습 최소 기준 미달", "지질 검진 기록 축적"],
  ["검증 표본이 작음", `검증 61명. 혈압 위험 ${tv.blood_pressure.final.actual_risk_n}건, 공복혈당 위험 ${tv.fasting_glucose.final.actual_risk_n}건`, "사용자 증가"],
], [3100, 3800, 2738], { zebra: false, compact: true });
table(["보완 과제", "현재 상태", "보완 방법"], [
  ["판정 기준표 확정", "학회 지침 기반 초안", "의료진 검토·승인, 지침 개정 시 설정 파일만 교체"],
  ["'주의' 판정이 넓음", `혈압 ${pct(tv.blood_pressure.final.pred_distribution["주의"] / tv.blood_pressure.n)}, 공복혈당 ${pct(tv.fasting_glucose.final.pred_distribution["주의"] / tv.fasting_glucose.n)}`, "'주의'는 재측정 안내, '위험'만 병원 안내"],
  ["가정혈압 기준 미적용", "가정혈압 고혈압 기준은 135/85 (진료실 140/90과 다름)", "웨어러블 혈압 표시 화면에는 가정혈압 기준 적용"],
  ["혈압계 측정 품질", "중앙 3회, 조건 비표준", "'아침 안정 시 2회' 측정 안내"],
  ["운영 자동화", "모델 갱신·산출이 수동", "주간 자동 갱신과 성능 추적"],
], [2700, 3200, 3738], { compact: true });
callout("다음 단계  ", "① 판정 기준표 의료진 승인  ② 기저질환 문진 항목 추가  ③ 검진 결과 업로드 캠페인('착용 뒤 검진' 30명)  ④ 가정 혈압 측정 안내.");

// ================= 부록 =================
ch.push(P([R("APPENDIX", { bold: true, color: C.blue, size: 24 })], { spacing: { before: 100, after: 80 }, pageBreakBefore: true }));
ch.push(P([R("부록. 건강검진 예측 항목별 가이드라인", { bold: true, size: 32 })], { spacing: { after: 120 } }));
ch.push(P([R("각 항목의 판정 기준을 출처별 원문 그대로 정리했습니다. 모든 수치는 2026-09-18에 원문(PubMed Central 전문, 학회 발간물, 국가법령정보센터)에서 직접 확인했습니다. 괄호 안 번호는 A-6 참고문헌 번호입니다.", { color: C.gray, size: 20 })], { spacing: { after: 160 } }));
const REFS = ["KSH2026", "KSH2022", "KSH2018", "KDA2025", "KDA2023", "KDA_KSoLA2023", "KSoLA2022", "KSoLA2018", "KSSO2022", "KSSO2024", "LEE2007", "NHS_KR"];
const n = k => `[${REFS.indexOf(k) + 1}]`;
h1("A-1. 혈압");
table(["기관 (출처)", "단계", "수축기 (mmHg)", "", "이완기 (mmHg)"], [
  [`대한고혈압학회 2026 ${n("KSH2026")}`, "정상혈압", "120 미만", "그리고", "80 미만"],
  ["", "주의혈압", "120~129", "그리고", "80 미만"],
  ["", "고혈압전단계", "130~139", "또는", "80~89"],
  ["", "고혈압 1기", "140~159", "또는", "90~99"],
  ["", "고혈압 2기", "160 이상", "또는", "100 이상"],
  [`국가건강검진 ${n("NHS_KR")}`, "정상A", "120 미만", "그리고", "80 미만"],
  ["", "정상B(경계)", "120~139", "또는", "80~89"],
  ["", "질환의심", "140 이상", "또는", "90 이상"],
  [`대한고혈압학회 2018·2022 ${n("KSH2018")}${n("KSH2022")}`, "가정혈압의 고혈압 기준", "135 이상", "또는", "85 이상"],
], [2900, 2300, 1700, 900, 1838], { zebra: false, compact: true });
table(["대상", "목표 혈압 (mmHg)", "출처"], [
  ["합병증 없는 고혈압(저·중위험), 노인", "140/90 미만", `${n("KSH2026")}${n("KSH2022")}`],
  ["고위험 고혈압, 심혈관질환", "130/80 미만", `${n("KSH2026")}${n("KSH2022")}`],
  ["당뇨병", "130/80 미만", `${n("KSH2026")}${n("KDA2025")}`],
  ["당뇨병 (이전 지침)", "저·중위험 140/90 미만, 고위험 130/80 미만", `${n("KSH2022")}${n("KDA2023")}`],
  ["만성콩팥병", "130/80 미만 (2022: 알부민뇨 없으면 140/90 미만)", `${n("KSH2026")}${n("KSH2022")}`],
  ["뇌졸중", "130/80 미만 (두개내 동맥 협착 동반 시 140/90 미만)", `${n("KSH2026")}`],
], [3600, 4400, 1638], { compact: true });
h1("A-2. 공복혈당");
table(["기관 (출처)", "단계", "공복혈당 (mg/dL)"], [
  [`대한당뇨병학회 2025 ${n("KDA2025")}`, "정상", "100 미만"],
  ["", "공복혈당장애 (당뇨병전단계)", "100~125"],
  ["", "당뇨병 진단 범위", "126 이상"],
  ["", "당뇨병 환자의 공복혈당 조절 목표", "80~130"],
  [`국가건강검진 ${n("NHS_KR")}`, "정상A / 정상B(경계) / 질환의심", "100 미만 / 100~125 / 126 이상"],
], [3000, 3700, 2938], { zebra: false, compact: true });
h1("A-3. 비만 (BMI · 허리둘레)");
table(["기관 (출처)", "단계", "기준"], [
  [`대한비만학회 2022 ${n("KSSO2022")}`, "저체중 / 정상", "BMI 18.5 미만 / 18.5~22.9"],
  ["", "비만전단계(과체중)", "BMI 23~24.9"],
  ["", "1단계 / 2단계 / 3단계 비만", "BMI 25~29.9 / 30~34.9 / 35 이상"],
  ["", "복부비만", `허리둘레 남 90 cm 이상, 여 85 cm 이상 (근거 연구 ${n("LEE2007")})`],
  [`대한비만학회 2024 ${n("KSSO2024")}`, "과체중 / 비만", "BMI 23 이상 / 25 이상 (기준 유지)"],
  [`국가건강검진 ${n("NHS_KR")}`, "정상A / 정상B(경계) / 질환의심", "BMI 18.5~24.9 / 25~29.9 / 18.5 미만 또는 30 이상"],
  ["", "허리둘레 정상A / 질환의심", "남 90 · 여 85 미만 / 이상"],
], [3000, 3000, 3638], { zebra: false, compact: true });
h1("A-4. 지질");
table(["기관 (출처)", "항목", "단계와 기준 (mg/dL)"], [
  [`한국지질동맥경화학회 2022 (5판) ${n("KSoLA2022")}`, "총콜레스테롤", "적정 200 미만 / 경계 200~239 / 높음 240 이상"],
  ["", "LDL 콜레스테롤", "적정 100 미만 / 정상 100~129 / 경계 130~159 / 높음 160~189 / 매우 높음 190 이상"],
  ["", "중성지방", "적정 150 미만 / 경계 150~199 / 높음 200~499 / 매우 높음 500 이상"],
  ["", "HDL 콜레스테롤", "낮음 40 미만 / 높음(바람직) 60 이상"],
  [`국가건강검진 ${n("NHS_KR")}`, "총콜레스테롤", "정상A 200 미만 / 경계 200~239 / 질환의심 240 이상"],
  ["", "LDL 콜레스테롤", "정상A 130 미만 / 경계 130~159 / 질환의심 160 이상 (당뇨병 동반 시 100 미만)"],
  ["", "중성지방", "정상A 150 미만 / 경계 150~199 / 질환의심 200 이상"],
  ["", "HDL 콜레스테롤", "정상A 60 이상 / 경계 40~59 / 질환의심 40 미만"],
], [3000, 1900, 4738], { zebra: false, compact: true });
table(["위험군", "LDL 목표 (mg/dL)", "출처"], [
  ["관상동맥질환 (초고위험)", "55 미만, 기저 대비 50% 이상 감소", `${n("KSoLA2022")}`],
  ["죽상경화성 뇌졸중·경동맥질환·말초동맥질환·복부대동맥류 (고위험)", "70 미만, 기저 대비 50% 이상 감소", `${n("KSoLA2022")}`],
  ["당뇨병: 유병 10년 미만, 주요 위험인자 없음", "100 미만", `${n("KSoLA2022")}${n("KDA2025")}${n("KDA_KSoLA2023")}`],
  ["당뇨병: 유병 10년 이상 또는 주요 위험인자·표적장기 손상", "70 미만", `${n("KSoLA2022")}${n("KDA2025")}${n("KDA_KSoLA2023")}`],
  ["당뇨병: 심혈관질환 동반, 또는 표적장기 손상·위험인자 3개 이상", "55 미만", `${n("KSoLA2022")}${n("KDA2025")}`],
  ["중등도 위험 (주요 위험인자 2개 이상) / 저위험 (1개 이하)", "130 미만 / 160 미만", `${n("KSoLA2022")}`],
], [5200, 2800, 1638], { compact: true });
h1("A-5. 출처 간 차이와 적용 원칙");
table(["항목", "차이", "적용"], [
  ["BMI", "대한비만학회는 25 이상을 비만, 국가검진은 25~29.9를 경계·30 이상을 질환의심으로 분류", "기본은 학회 기준(더 이른 경계). 두 단계명을 모두 산출"],
  ["당뇨병 환자의 혈압 목표", "2022~2023 지침은 저위험군 140/90 미만 허용, 2025~2026 지침은 130/80 미만으로 통일", "최신이자 더 엄격한 130/80 미만을 기본 적용, 이전 기준도 보존"],
  ["만성콩팥병의 혈압 목표", "2022 지침은 알부민뇨 유무로 구분, 2026 지침은 130/80 미만", "130/80 미만 기본 적용"],
  ["LDL", "진단 구간(130·160)과 위험군별 치료 목표(55~160)는 다른 축", "질환 미상은 진단 구간, 질환 확인 시 치료 목표"],
  ["혈압 측정 환경", "진료실 140/90, 가정혈압 135/85", "검진 예측값은 진료실 기준. 웨어러블 측정값 화면은 가정혈압 기준 권장"],
], [2000, 4500, 3138], { compact: true });
h1("A-6. 참고문헌", true);
REFS.forEach((k, i) => { const s = S[k]; const ids = [s.pmid ? `PMID: ${s.pmid}` : null, s.doi ? `DOI: ${s.doi}` : null, s.pmcid ? `PMCID: ${s.pmcid}` : null, s.url ? s.url : null].filter(Boolean).join(" · ");
  ch.push(new Paragraph({ spacing: { after: 90, line: 270, lineRule: "auto" }, indent: { left: 420, hanging: 420 }, children: [R(`[${i + 1}] `, { bold: true, color: C.navy, size: 18 }), R(`${s.org}. `, { bold: true, size: 18 }), R(`${s.title}. ${s.citation}. `, { size: 18 }), R(ids || "식별자 없음", { color: C.blue, size: 18 }), ...(s.note ? [R(`  ※ ${s.note}`, { color: C.gray, size: 17 })] : [])] })); });
src("PMID·DOI는 PubMed(NCBI E-utilities)에서 조회해 확인했습니다. [7]은 학회 발간 요약본으로 PubMed 등재 논문을 확인하지 못했고, [12]는 정부 고시로 최신 고시 번호를 확인하지 못했습니다. 본 기준표는 의료진 승인 전 초안이며, 본 모델은 진단·치료가 아닌 검진·진료 안내 보조 도구입니다.");

const footer = new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TW }], children: [
  new TextRun({ text: "건강검진 예측 모델 결과 보고서 · 헬스커넥트(주) · 대외비", color: C.gray, size: 16 }), new TextRun({ text: "\t", color: C.gray, size: 16 }), new TextRun({ children: [PageNumber.CURRENT], color: C.gray, size: 16 })] })] });
const doc = new Document({
  styles: { default: { document: { run: { font: "Pretendard", color: C.text, size: 20 } } }, paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Pretendard", bold: true, color: C.navy, size: 28 }, paragraph: { outlineLevel: 0 } }] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "●", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } }, run: { color: C.gray, size: 12 } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134, header: 708, footer: 708 } } }, footers: { default: footer }, children: ch }],
});
Packer.toBuffer(doc).then(buf => { const out = "/Users/jaeho.oh/Downloads/SiBC_건강검진예측모델_결과보고서_20260918.docx"; fs.writeFileSync(out, buf); console.log("written", out, buf.length); });
