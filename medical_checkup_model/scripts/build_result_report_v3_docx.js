// 결과 보고서 v3(수치 예측 전용: 판정·안내는 판단 Agent 담당이므로 제외). 원본 주석: 결과 보고서(첫 보고용): 과거 데이터셋·이전 모델과의 비교 없이 '최신 데이터셋으로 만든 모델의 결과와 제한' 중심. 원본 주석: 고도화 결과 보고서 v2 — 경영진 보고용 간결판(2쪽 핵심 요약 + 본문 6장). 헬퍼는 v1과 동일 — 원본 주석: 모델 분석 보고서 v3 — v2(푸드렌즈 템플릿 포맷)에서 (1) 표 테두리를 표 단위로 통일(뷰어별 선 어긋남 방지), (2) '봉인' 등 전문 용어를 쉬운 말로 교체,
// (3) 보고서 구성표·장별 요점·그림 번호(1~6) 상호참조를 추가해 추적성을 높임. 실행: NODE_PATH=<docx 위치> node scripts/build_analysis_report_v3_docx.js
const fs = require("fs"), path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel, LevelFormat, ImageRun, Footer, PageNumber, TabStopType, VerticalAlign, TableLayoutType } = require("docx");
const ROOT = path.join(__dirname, ".."), ASSETS = path.join(__dirname, "prediction_assets");
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




const sg = sig.m1, fu = m2.fusion, tp = m2.temporal, nc = m2.noise_ceiling, ab = m2.history_ablation;
const ps = J("01_Results/predictions/prediction_summary.json"), sch = J("configs/prediction_output_schema.json");
const wn = ds.wearable_now, bf = wn.by_feature, fn = ds.forward_now, ln = ds.labels_now;
const pct = x => Math.round(x * 100) + "%";
const gain = k => Math.round((1 - sg[k].mae_model / sg[k].mae_cf) * 100);
const room = Math.round((1 - nc.sbp.mae_floor_estimate / sg.sbp.mae_model) * 100);
const cov = ps.coverage, served = k => Object.entries(cov[k]).filter(([r]) => r !== "ABSTAIN").reduce((a, [, v]) => a + v, 0);
const KOR = { sbp: "수축기혈압", dbp: "이완기혈압", fasting_glucose: "공복혈당", weight: "체중", bmi: "BMI", waist: "허리둘레", total_cholesterol: "총콜레스테롤", hdl: "HDL", ldl: "LDL", triglyceride: "중성지방" };
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
ch.push(P([R("예측 수치의 정확도 · 산출 범위 · 판단 Agent 연계 명세 · 제한사항", { size: 30 })], { spacing: { after: 5200 } }));
ch.push(P([R("오재호 과장", { bold: true, size: 26 })], { spacing: { after: 55 } }));
ch.push(P([R("AI플랫폼본부 SiBC · 데이터 기준일 2026-09-17 · 산출일 2026-09-18", { color: C.gray })], { spacing: { after: 36 } }));

// ================= 핵심 요약 =================
ch.push(P([R("EXECUTIVE SUMMARY", { bold: true, color: C.blue, size: 24 })], { spacing: { before: 90, after: 80 }, pageBreakBefore: true }));
ch.push(P([R("핵심 요약", { bold: true, size: 32 })], { spacing: { after: 140 } }));
callout("결론  ", `과거 검진 기록과 웨어러블 측정값으로 건강검진 10개 항목의 수치를 추정하는 모델을 구축했습니다. 모델은 항목별 예측값과 85% 예측 구간, 산출 근거만 내보내고, 주의·위험 판정과 의료진 안내는 후단 판단 Agent가 담당합니다. 혈압·공복혈당은 직전 검진값보다 유의하게 정확하고 예측 구간은 명목 적중률을 충족합니다. 걸음·심박·수면의 효과는 검증용 데이터가 부족해 아직 반영하지 못했습니다.`);
ch.push(P([], { spacing: { after: 120 } }));
kpi([
  { label: "혈압 예측 오차", value: `−${gain("sbp")}% · −${gain("dbp")}%`, note: "직전 검진값 그대로 대비 수축기·이완기. 통계적으로 유의", fill: C.mint, color: C.green },
  { label: "85% 구간 적중률", value: `${Math.round(ps.picp.sbp * 100)}~${Math.round(Math.max(...Object.values(ps.picp)) * 100)}%`, note: `10개 항목 중 9개가 80% 이상. 공복혈당 ${Math.round(ps.picp.fasting_glucose * 100)}%`, fill: C.mint, color: C.green },
  { label: "산출 대상 사용자", value: `${ps.users}명`, note: `검진 보유 ${ps.with_checkup}명 + 웨어러블만 있는 ${ps.users - ps.with_checkup}명. 사용자×항목 ${ps.rows.toLocaleString()}행` },
  { label: "걸음·심박·수면 학습 데이터", value: `${fn.users_ge1d} / 30명`, note: "'착용 뒤 검진' 기록. 기준 미달로 미반영", fill: C.rose, color: C.red },
]);
sub("결과 요약");
table(["구분", "결과", "판정"], [
  ["모델 범위", "입력: 과거 검진값·경과일·추세, 성별·연령, 웨어러블 혈압계·체중계 측정값 → 출력: 항목별 예측값·85% 구간·산출 경로·근거. 상태 판정은 하지 않음", "판단 Agent 연계"],
  ["사용 데이터", `웨어러블 ${wn.users}명, 검진 ${ln.users}명(${ln.events.toLocaleString()}건), 공공데이터 약 1만 건(학습 전용). 평가는 자체 데이터로만 수행`, "—"],
  hl(["혈압·공복혈당 수치", `직전 검진값 대비 오차 −${gain("sbp")}% / −${gain("dbp")}% / −${gain("fasting_glucose")}%. 혈압은 시간 순서 검증도 통과`, "근거 등급 A"], C.mint),
  hl(["예측 구간", `85% 구간의 실제 적중률 ${Math.round(ps.picp.fasting_glucose * 100)}~${Math.round(Math.max(...Object.values(ps.picp)) * 100)}%. 폭은 수축기 ±${(ps.width.sbp / 2).toFixed(1)} mmHg, 공복혈당 ±${(ps.width.fasting_glucose / 2).toFixed(1)} mg/dL`, "판단 시 상한 함께 사용"], C.mint),
  hl(["웨어러블 측정값 활용", `체중계 측정값으로 체중 오차 ${fu.weight.with_prior_checkup.mae_base}→${fu.weight.with_prior_checkup.mae_fused} kg. 검진 이력 없는 사용자에게 체중·수축기혈압 제공. 혈압계 측정값은 효과 없음`, "체중만 채택"], C.amber),
  ["체중·BMI·허리둘레, 지질", "직전 검진값이 이미 정확하거나(체중·BMI) 반복 검진이 적음(지질). 직전값 유지 또는 다른 항목 기반", "근거 등급 B·C"],
  hl(["제한", `걸음·심박·수면은 '착용 뒤 검진' 30명 확보 전까지 반영 불가. 수치 예측은 검진값 자체의 변동 때문에 남은 개선 여지 약 ${room}%`, "데이터·시간 필요"], C.rose),
], [2100, 6000, 1538], { zebra: false });
sub("결정이 필요한 사항");
bullet("판단 Agent 연계 명세 확정.", "출력 필드(예측값·구간·경로·근거 등급·보류 사유)를 3장 명세로 고정했습니다. Agent 측 요구가 있으면 반영합니다.");
bullet("검진 결과 업로드 캠페인.", "'착용 뒤 검진' 30명 확보가 걸음·심박·수면 반영의 유일한 경로입니다. 3~6개월이 걸립니다.");
bullet("가정 혈압 측정 안내.", "측정 횟수와 조건이 표준화되어야 혈압계 데이터로 혈압 예측을 개선할 수 있습니다.");

// ================= 본문 =================
h1("1. 모델 개요와 사용 데이터", true);
table(["구분", "내용"], [
  ["역할", "웨어러블·검진 이력으로 '오늘 검진하면 나올 값'을 항목별로 추정. 상태 판정·안내는 판단 Agent 담당"],
  ["예측 항목", "혈압(수축기·이완기), 공복혈당, 체중·BMI·허리둘레, 총콜레스테롤·LDL·HDL·중성지방 (10개)"],
  ["입력", "과거 검진값과 경과일·추세, 성별·연령, 기준일 이전 180일 웨어러블 혈압계·체중계 측정값"],
  ["출력", "예측값, 85% 예측 구간(하한·상한), 산출 경로, 근거 등급(A/B/C), 보류 사유, 근거 데이터(직전 검진값·경과일, 측정 중앙값·횟수·기간)"],
  ["학습 데이터", `자체 검진 ${ln.events.toLocaleString()}건(${ln.users}명) + 공공데이터(미국 NHANES 9,981건, 한국 KNHANES 592건). 공공데이터는 학습에만 사용`],
  ["검증 방법", "학습에 쓰지 않은 사용자 61명으로 1회 평가. 비교 기준은 '직전 검진값 그대로'. 개선 여부는 사용자 단위 부트스트랩 95% 신뢰구간으로 판정"],
], [1900, 7738], { compact: true });
body(`그림 1의 왼쪽은 데이터 종류별 사용자 수입니다. 웨어러블 사용자 ${wn.users}명 가운데 혈압계 측정 ${bf.bp_systolic_measured.users}명, 체중계 측정 ${bf.body_weight_measured.users}명이 가장 많고, 검진 기록 보유자는 ${ln.users}명입니다. 오른쪽은 걸음·심박·수면을 모델 입력으로 쓰기 위해 필요한 '웨어러블 착용 뒤에 받은 검진' 기록으로, 현재 ${fn.users_ge1d}명이어서 학습·검증 시작 기준인 30명에 미치지 못합니다. 걸음·심박·수면 기록 자체는 ${bf.step_count.users}명·${bf.heartrate_median.users}명·${bf.sleep_duration_min.users}명에게 쌓여 있지만 검진값과의 관계를 배울 예시가 부족해, 이번 모델에는 검진값과 직접 대응되는 혈압계·체중계 측정값만 반영했습니다.`);
figure(1, "보유 데이터와 학습 데이터 부족", "P1_data.png", "", 470, 268);

h1("2. 수치 예측 성능", true);
table(["항목", "오차: 직전값 → 모델", "개선", "시간 순서 검증", "산출 경로"], [
  ["수축기혈압", `${sg.sbp.mae_cf} → ${sg.sbp.mae_model} mmHg`, `−${gain("sbp")}%, 유의`, `−${tp.sbp.improve_pct}%, 통과`, "개인화 모델"],
  ["이완기혈압", `${sg.dbp.mae_cf} → ${sg.dbp.mae_model} mmHg`, `−${gain("dbp")}%, 유의`, `−${tp.dbp.improve_pct}%, 통과`, "개인화 모델"],
  ["공복혈당", `${sg.fasting_glucose.mae_cf} → ${sg.fasting_glucose.mae_model} mg/dL`, `−${gain("fasting_glucose")}%, 유의`, `−${tp.fasting_glucose.improve_pct}%, 경계`, "개인화 모델"],
  ["체중 · BMI · 허리둘레", "모델 개선 3% 미달", "—", "—", "직전값 유지 (+체중 융합)"],
  ["지질 4종", "반복 검진 63명, 설명력 낮음", "—", "—", "직전값 유지 / 다른 항목 기반"],
], [2100, 2700, 1500, 1700, 1638], { compact: true });
body(`그림 2는 항목별 평균 오차를 세 가지로 비교합니다. 연한 파랑은 직전 검진값을 그대로 쓴 경우, 진한 파랑은 예측 모델, 회색은 같은 사람의 검진값이 검진마다 자연스럽게 흔들리는 폭에서 추정한 오차의 하한입니다. 혈압은 모델이 직전값보다 ${gain("sbp")}%·${gain("dbp")}% 정확하며, 하한까지 남은 여지는 약 ${room}%입니다. 공복혈당은 하한 추정에 실제 변화가 섞여 모델보다 높게 나왔습니다. 시간 순서 검증은 2025년 이전 검진으로 학습하고 이후 검진을 맞히는 방식으로, 실제 서비스와 같은 조건에서도 혈압 예측의 개선이 유지됐습니다.`);
figure(2, "수치 예측 정확도", "P2_accuracy.png", "", 430, 245);
body(`예측값은 실제 고위험자의 값을 낮게 보는 경향이 있습니다. 검증에서 실제 수축기혈압이 140 이상인 사람은 평균 ${Math.abs(m2.calibration.sbp.actual_high.bias_pred_minus_actual)} mmHg 낮게, 공복혈당이 126 이상인 사람은 ${Math.abs(m2.calibration.fasting_glucose.actual_high.bias_pred_minus_actual)} mg/dL 낮게 예측됩니다. 이는 보정으로 고칠 수 있는 편향이 아니라 평균 회귀 현상이며(재보정 후에도 변화 없음), 그래서 모델은 점추정과 함께 예측 구간을 내보냅니다. 그림 3의 왼쪽은 85% 예측 구간이 실제값을 담은 비율로, 10개 항목 중 9개가 80% 이상이고 공복혈당만 ${Math.round(ps.picp.fasting_glucose * 100)}%입니다. 오른쪽은 구간의 폭입니다. 판단 Agent가 위험 여부를 정할 때는 점추정만이 아니라 상한을 함께 보는 것이 안전합니다.`);
figure(3, "예측 구간의 적중률과 폭", "P3_interval.png", "", 440, 251);

h1("3. 판단 Agent 연계 출력 명세");
body(`모델은 사용자×항목 단위의 long 형식(${ps.rows.toLocaleString()}행)과 사용자당 1행의 wide 형식을 함께 저장합니다. 명세는 설정 파일로 고정했으며(버전 ${sch.version}), 정상·주의·위험 판정, 기준 초과 확률, 의료진 안내, 변화 방향은 포함하지 않습니다.`);
table(["필드", "의미"], [
  ["user_key, prediction_index_time", "가명 사용자 키, 예측 기준일. 기준일 이전 데이터만 사용"],
  ["item, unit", "항목 코드(sbp, dbp, fasting_glucose, weight, bmi, waist, total_cholesterol, hdl, ldl, triglyceride)와 단위"],
  ["value, lower, upper, interval_level", "예측값(점추정), 85% 예측 구간 하한·상한. 보류 시 null"],
  ["route", "산출 경로: M1_MODEL(개인화 모델) / CARRY_FORWARD(직전 검진값) / MODEL_CROSS(다른 항목 기반) / FUSION(검진+웨어러블 융합) / FUSION_DERIVED(융합 체중→BMI) / M0_MEASURED(이력 없음, 측정값+성별·연령 기준) / ABSTAIN(보류)"],
  ["evidence_level", "근거 등급. A: 검증에서 직전값 대비 유의 개선 · B: 직전값 유지, 조건부 채택 · C: 참고(검증 표본 부족)"],
  ["abstain_reason", "보류 사유: no_prior_checkup(직전 검진 없음), stale_anchor(직전 검진 3년 초과), no_checkup_history(검진 이력 없음), no_rule"],
  ["basis_prev_checkup_*", "직전 검진 실제값, 검진일, 경과일"],
  ["basis_wearable_*", "기준일 이전 180일 웨어러블 측정 중앙값, 횟수, 첫날·마지막 날 (혈압계·체중계)"],
  ["model_version", "개인화 모델 버전 + 융합 모델 버전"],
], [3000, 6638], { compact: true });
body(`그림 4는 항목별로 어떤 경로로 값을 산출했는지 보여 줍니다. 진한 파랑은 개인화 모델, 파랑 계열은 융합·직전값·다른 항목 기반, 밝은 파랑은 검진 이력이 없는 사용자에게 웨어러블 측정값으로 산출한 경우, 회색은 근거가 부족해 보류한 사용자입니다. 혈압·공복혈당은 ${served("sbp")}·${served("dbp")}·${served("fasting_glucose")}명, 체중은 ${served("weight")}명에게 값을 제공합니다. 보류 사유는 직전 검진 없음 ${ps.abstain_reasons.no_prior_checkup || 0}건, 직전 검진 3년 초과 ${Object.entries(ps.abstain_reasons).filter(([k]) => k.startsWith("stale")).reduce((a, [, v]) => a + v, 0)}건입니다.`);
figure(4, "항목별 산출 범위와 산출 경로", "P5_coverage.png", "", 460, 263);
table(["항목", "산출 경로별 사용자 수", "근거 등급"], [
  ...["sbp", "dbp", "fasting_glucose", "weight", "bmi", "waist", "total_cholesterol", "hdl", "ldl", "triglyceride"].map(k => {
    const c = cov[k], parts = [["M1_MODEL", "개인화"], ["FUSION", "융합"], ["FUSION_DERIVED", "융합 파생"], ["CARRY_FORWARD", "직전값"], ["MODEL_CROSS", "다른 항목"], ["M0_MEASURED", "이력 없음"], ["ABSTAIN", "보류"]].filter(([r]) => c[r]).map(([r, n]) => `${n} ${c[r]}`).join(" · ");
    const e = ps.evidence[k]; return [KOR[k], parts, ["A", "B", "C"].filter(l => e[l]).map(l => `${l} ${e[l]}`).join(" · ")]; }),
], [1800, 5300, 2538], { compact: true });

h1("4. 웨어러블 측정값 활용");
body(`검진일 전후 180일 안에 웨어러블 측정이 있는 검진을 짝지어(혈압 ${fu.sbp.n_pairs}쌍, 체중 ${fu.weight.n_pairs}쌍) 사용자 단위 5겹 교차검증을 10회 반복했습니다. 채택 규칙은 '기존 예측 대비 오차 차이의 95% 구간이 0 미만이면 채택, 개선 3% 이상이면서 더 넓은 창(±365일)에서 유의하면 조건부 채택'입니다. 그림 5의 왼쪽은 직전 검진이 있는 사용자에서 검진 이력만 쓴 예측(연한 파랑)과 웨어러블 측정값을 더한 예측(진한 파랑)의 평균 오차, 오른쪽은 검진 이력이 없다고 가정했을 때 성별·연령 평균(회색)과 측정값 반영(파랑)의 오차입니다. 막대 위 글씨가 채택 판정입니다.`);
figure(5, "웨어러블 측정값의 효과", "P4_wearable.png", "", 500, 286);
table(["대상", "항목", "오차 변화", "판정"], [
  hl(["검진 이력 있음", "체중 (BMI 파생)", `${fu.weight.with_prior_checkup.mae_base} → ${fu.weight.with_prior_checkup.mae_fused} kg`, "조건부 채택 (표본 추가 후 재평가)"], C.amber),
  ["검진 이력 있음", "수축기 / 이완기혈압", `${fu.sbp.with_prior_checkup.mae_base} → ${fu.sbp.with_prior_checkup.mae_fused} / ${fu.dbp.with_prior_checkup.mae_base} → ${fu.dbp.with_prior_checkup.mae_fused}`, "미채택 (개선 없음)"],
  hl(["검진 이력 없음", "체중", `성별·연령 평균 ${fu.weight.no_prior_checkup.mae_korean_reference_only} → ${fu.weight.no_prior_checkup.mae_m0_measured} kg`, "채택"], C.mint),
  hl(["검진 이력 없음", "수축기혈압", `${fu.sbp.no_prior_checkup.mae_korean_reference_only} → ${fu.sbp.no_prior_checkup.mae_m0_measured} mmHg`, "채택 (근거 등급 C)"], C.mint),
  ["검진 이력 없음", "이완기혈압", `${fu.dbp.no_prior_checkup.mae_korean_reference_only} → ${fu.dbp.no_prior_checkup.mae_m0_measured}`, "미채택"],
], [2000, 2300, 3100, 2238], { zebra: false, compact: true });
body(`혈압계 측정값이 도움이 되지 않은 이유는 측정 횟수가 적고(중앙 3회) 측정 자세·시간이 표준화돼 있지 않기 때문입니다. 방문 이력 통계와 다른 혈액 항목을 입력에 추가하는 방법도 시험했으나 개선이 최대 ${Math.max(ab.sbp.best_gain_pct, ab.dbp.best_gain_pct, ab.fasting_glucose.best_gain_pct)}%에 그쳐 채택하지 않았습니다.`);

h1("5. 제한사항과 보완 계획", true);
table(["제한 (현재 해결 불가)", "이유", "풀리는 조건"], [
  hl(["걸음·심박·수면을 입력으로 사용", `'착용 뒤 검진' 기록 ${fn.users_ge1d}명. 학습·검증 모두 불가`, "30명 이상 확보 (3~6개월)"], C.rose),
  hl(["수치 예측 정확도의 상한", `검진값 자체가 같은 사람도 ±${nc.sbp.sigma_within} mmHg 변동. 남은 여지 약 ${room}%`, "반복 측정으로 기준값의 변동을 줄여야 함"], C.rose),
  ["고위험 구간의 과소 예측", "평균 회귀 현상. 재보정으로 교정되지 않음", "판단 Agent가 예측 구간 상한을 함께 사용"],
  ["혈당·지질의 웨어러블 추정", "측정 채널 없음", "연속혈당측정기 등 기기 연동"],
  ["검진 이력 없는 사용자의 이완기·혈당·지질·BMI", "측정값 효과 없음 또는 키 정보 없음", "첫 검진 업로드, 프로필 키 수집"],
  ["검증 표본이 작음", "검증 61명. 구간 적중률·개선폭의 신뢰구간이 넓음", "사용자 증가"],
], [3100, 3800, 2738], { zebra: false, compact: true });
table(["보완 과제", "현재 상태", "보완 방법"], [
  ["판단 Agent 연계 검증", "출력 명세 v1.0 고정, Agent 측 요구 미반영", "Agent가 쓰는 필드·형식 확인 후 명세 확정"],
  ["공복혈당 구간 적중률·시간 순서 검증", `적중률 ${Math.round(ps.picp.fasting_glucose * 100)}%, 시간 순서 개선은 경계`, "분기마다 재검증, 구간 보정 재적합"],
  ["체중 융합 조건부 채택", "검증 쌍 70개", "100쌍 이상에서 재평가"],
  ["혈압계 측정 품질", "중앙 3회, 조건 비표준", "'아침 안정 시 2회' 측정 안내"],
  ["운영 자동화", "모델 갱신·산출이 수동", "주간 자동 갱신과 성능·적중률 추적"],
], [2700, 3200, 3738], { compact: true });
callout("다음 단계  ", "① 판단 Agent와 출력 명세 확정  ② 검진 결과 업로드 캠페인('착용 뒤 검진' 30명)  ③ 가정 혈압 측정 안내  ④ 주간 자동 갱신.");
src("근거 파일: 01_Results/predictions/predictions_long_2026-09-18.parquet(가명키) · configs/prediction_output_schema.json · 01_Results/significance.json · 01_Results/m2/m2_report.json. 본 모델은 진단·치료가 아닌 검진·진료 안내 보조 도구의 수치 입력을 제공합니다.");

const footer = new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TW }], children: [
  new TextRun({ text: "건강검진 예측 모델 결과 보고서 · 헬스커넥트(주) · 대외비", color: C.gray, size: 16 }), new TextRun({ text: "\t", color: C.gray, size: 16 }), new TextRun({ children: [PageNumber.CURRENT], color: C.gray, size: 16 })] })] });
const doc = new Document({
  styles: { default: { document: { run: { font: "Pretendard", color: C.text, size: 20 } } }, paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Pretendard", bold: true, color: C.navy, size: 28 }, paragraph: { outlineLevel: 0 } }] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "●", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } }, run: { color: C.gray, size: 12 } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134, header: 708, footer: 708 } } }, footers: { default: footer }, children: ch }],
});
Packer.toBuffer(doc).then(buf => { const out = "/Users/jaeho.oh/Downloads/SiBC_건강검진예측모델_결과보고서_20260918.docx"; fs.writeFileSync(out, buf); console.log("written", out, buf.length); });
