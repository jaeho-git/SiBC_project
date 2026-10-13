// 결과 보고서(첫 보고용): 과거 데이터셋·이전 모델과의 비교 없이 '최신 데이터셋으로 만든 모델의 결과와 제한' 중심. 원본 주석: 고도화 결과 보고서 v2 — 경영진 보고용 간결판(2쪽 핵심 요약 + 본문 6장). 헬퍼는 v1과 동일 — 원본 주석: 모델 분석 보고서 v3 — v2(푸드렌즈 템플릿 포맷)에서 (1) 표 테두리를 표 단위로 통일(뷰어별 선 어긋남 방지), (2) '봉인' 등 전문 용어를 쉬운 말로 교체,
// (3) 보고서 구성표·장별 요점·그림 번호(1~6) 상호참조를 추가해 추적성을 높임. 실행: NODE_PATH=<docx 위치> node scripts/build_analysis_report_v3_docx.js
const fs = require("fs"), path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel, LevelFormat, ImageRun, Footer, PageNumber, TabStopType, VerticalAlign, TableLayoutType } = require("docx");
const ROOT = path.join(__dirname, ".."), ASSETS = path.join(__dirname, "result_assets");
const J = f => JSON.parse(fs.readFileSync(path.join(ROOT, f), "utf8"));
const audit = J("01_Results/model_audit.json"), m2 = J("01_Results/m2/m2_report.json"), ds = J("01_Results/data_status_2026-09-17.json"), up = J("01_Results/m2/upgrade_summary.json");
const old = J("01_Results/snapshots/2026-09-10_before_rebuild/significance.json"), oldAudit = J("01_Results/snapshots/2026-09-10_before_rebuild/model_audit.json");
const sig = JSON.parse(fs.readFileSync(path.join(ROOT, "01_Results/significance.json"), "utf8"));
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
  ch.push(new Paragraph({ keepNext: true, alignment: AlignmentType.CENTER, children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(ASSETS, file)), transformation: { width: w, height: h } })] }));
  ch.push(P([R("읽는 법: " + caption, { color: C.gray, size: 17 })], { spacing: { before: 60, after: 200 } }));
}


const sg = sig.m1, fu = m2.fusion, rf = m2.referral, tp = m2.temporal, nc = m2.noise_ceiling, ab = m2.history_ablation;
const rs = J("01_Results/m2/result_summary.json");
const wn = ds.wearable_now, bf = wn.by_feature, fn = ds.forward_now, ln = ds.labels_now;
const pct = x => Math.round(x * 100) + "%";
const fv = k => rf[k].final_validation, RT = "rule_referral_threshold", HT = "hypertension_140_90";
const gain = k => Math.round((1 - sg[k].mae_model / sg[k].mae_cf) * 100);
const room = Math.round((1 - nc.sbp.mae_floor_estimate / sg.sbp.mae_model) * 100);
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
ch.push(P([R("모델 성능 · 활용 가능 범위 · 제한사항", { size: 30 })], { spacing: { after: 5200 } }));
ch.push(P([R("오재호 과장", { bold: true, size: 26 })], { spacing: { after: 55 } }));
ch.push(P([R("AI플랫폼본부 SiBC · 데이터 기준일 2026-09-17", { color: C.gray })], { spacing: { after: 36 } }));

// ================= 핵심 요약 =================
ch.push(P([R("EXECUTIVE SUMMARY", { bold: true, color: C.blue, size: 24 })], { spacing: { before: 90, after: 80 }, pageBreakBefore: true }));
ch.push(P([R("핵심 요약", { bold: true, size: 32 })], { spacing: { after: 140 } }));
callout("결론  ", `과거 검진 기록과 웨어러블 측정값으로 혈압·혈당·체중을 추정하고 고위험자를 안내하는 모델을 구축했습니다. 혈압·혈당 예측과 고위험 안내는 의료진 검토용으로 쓸 수 있는 수준입니다. 걸음·심박·수면의 효과는 검증용 데이터가 부족해 아직 확인할 수 없습니다.`);
ch.push(P([], { spacing: { after: 120 } }));
kpi([
  { label: "혈압 예측 오차", value: `−${gain("sbp")}% · −${gain("dbp")}%`, note: "직전 검진값을 그대로 쓰는 것 대비 수축기·이완기. 통계적으로 유의", fill: C.mint, color: C.green },
  { label: "고혈압 대상자 발견", value: `${fv(HT)[RT].positives - fv(HT)[RT].missed} / ${fv(HT)[RT].positives}명`, note: `찾아낸 비율 ${pct(fv(HT)[RT].sensitivity)}. 4개 안내 항목 모두 85% 이상`, fill: C.mint, color: C.green },
  { label: "산출 대상 사용자", value: `${rs.users}명`, note: `검진 보유 ${rs.with_checkup}명 + 웨어러블만 있는 ${rs.no_checkup}명` },
  { label: "걸음·심박·수면 검증 데이터", value: `${fn.users_ge1d} / 30명`, note: "'착용 뒤 검진' 기록. 기준 미달로 검증 불가", fill: C.rose, color: C.red },
]);
sub("결과 요약");
table(["구분", "결과", "판정"], [
  ["사용 데이터", `웨어러블 ${wn.users}명, 검진 ${ln.users}명(${ln.events.toLocaleString()}건), 공공데이터 약 1만 건(학습 전용). 평가는 자체 데이터로만 수행`, "—"],
  hl(["혈압·혈당 수치 예측", `직전 검진값 대비 오차 −${gain("sbp")}% / −${gain("dbp")}% / −${gain("fasting_glucose")}% (수축기 / 이완기 / 공복혈당). 혈압은 시간 순서 검증도 통과`, "의료진 검토용"], C.mint),
  hl(["고위험 안내 (고혈압·혈당장애·비만·복부비만)", `기준 초과자를 ${pct(fv(HT)[RT].sensitivity)} / ${pct(fv("fasting_glucose_ge100")[RT].sensitivity)} / ${pct(fv("obesity_bmi_ge25")[RT].sensitivity)} / ${pct(fv("abdominal_obesity")[RT].sensitivity)} 찾아냄. 낮음·주의·높음 3단계 제공`, "의료진 검토용"], C.mint),
  hl(["웨어러블 측정값 활용", `체중계 측정값으로 체중 오차 ${fu.weight.with_prior_checkup.mae_base}→${fu.weight.with_prior_checkup.mae_fused} kg. 검진 이력 없는 사용자에게 체중·수축기혈압 제공. 혈압계 측정값은 효과 없음`, "체중만 채택"], C.amber),
  ["체중·BMI·허리둘레, 지질", "직전 검진값이 이미 정확하거나(체중·BMI) 설명력이 낮음(지질)", "참고용"],
  hl(["제한", `걸음·심박·수면의 효과는 검증 데이터 30명 확보 전까지 확인 불가. 수치 예측은 검진값 자체의 변동 때문에 남은 개선 여지 약 ${room}%`, "데이터·시간 필요"], C.rose),
], [2500, 5600, 1538], { zebra: false });
sub("결정이 필요한 사항");
bullet("안내 기준점 승인.", `고혈압 대상자를 ${pct(fv(HT)[RT].sensitivity)} 찾아내는 대신 사용자의 ${pct(fv(HT)[RT].flagged_rate)}가 '주의' 이상이 됩니다. 의료진과 기준 확정이 필요합니다.`);
bullet("검진 결과 업로드 캠페인.", "'착용 뒤 검진' 30명 확보가 웨어러블 효과 검증의 유일한 경로입니다. 3~6개월이 걸립니다.");
bullet("가정 혈압 측정 안내.", "측정 횟수와 조건이 표준화되어야 혈압계 데이터를 모델에 쓸 수 있습니다.");

// ================= 본문 =================
h1("1. 모델 개요와 사용 데이터", true);
point("검진 이력이 있으면 과거 검진값 중심으로, 없으면 웨어러블 측정값 중심으로 현재 검진 수치를 추정합니다.");
table(["구분", "내용"], [
  ["예측 대상", "혈압(수축기·이완기), 공복혈당, 체중·BMI·허리둘레, 지질 4종. 고혈압·혈당장애·비만·복부비만 안내"],
  ["입력", "과거 검진값과 경과일·추세, 성별·연령, 웨어러블 혈압계·체중계 측정값"],
  ["출력", "예측값과 85% 구간, 위험 등급(낮음·주의·높음), 근거가 부족하면 '보류'와 사유"],
  ["학습 데이터", `자체 검진 ${ln.events.toLocaleString()}건(${ln.users}명) + 공공데이터(미국 NHANES 9,981건, 한국 KNHANES 592건). 공공데이터는 학습에만 사용`],
  ["검증 방법", "학습에 쓰지 않은 사용자 61명으로 1회 평가. 비교 기준은 '직전 검진값 그대로'"],
], [1900, 7738], { compact: true });
figure(1, "보유 데이터와 검증 데이터 부족", "R1_data.png", "왼쪽은 데이터 종류별 사용자 수, 오른쪽은 걸음·심박·수면의 효과를 검증하는 데 필요한 '착용 뒤 검진' 기록과 기준 30명입니다.", 470, 268);
body(`걸음·심박·수면은 ${bf.step_count.users}명·${bf.heartrate_median.users}명·${bf.sleep_duration_min.users}명에게 쌓여 있지만, 이 신호가 검진값과 어떻게 연결되는지 배우려면 웨어러블을 착용한 뒤에 받은 검진 기록이 필요합니다. 현재 ${fn.users_ge1d}명뿐이라 이번 모델에는 검진값과 직접 대응되는 혈압계·체중계 측정값만 반영했습니다.`);

h1("2. 수치 예측 성능");
point(`혈압·공복혈당은 직전 검진값보다 ${gain("dbp")}~${gain("sbp")}% 정확합니다. 체중·BMI는 직전 검진값이 이미 충분히 정확합니다.`);
table(["항목", "오차: 직전값 → 모델", "개선", "시간 순서 검증", "판정"], [
  ["수축기혈압", `${sg.sbp.mae_cf} → ${sg.sbp.mae_model} mmHg`, `−${gain("sbp")}%, 유의`, `−${tp.sbp.improve_pct}%, 통과`, "채택"],
  ["이완기혈압", `${sg.dbp.mae_cf} → ${sg.dbp.mae_model} mmHg`, `−${gain("dbp")}%, 유의`, `−${tp.dbp.improve_pct}%, 통과`, "채택"],
  ["공복혈당", `${sg.fasting_glucose.mae_cf} → ${sg.fasting_glucose.mae_model} mg/dL`, `−${gain("fasting_glucose")}%, 유의`, `−${tp.fasting_glucose.improve_pct}%, 경계`, "채택"],
  ["체중 · BMI · 허리둘레", "모델 개선 3% 미달", "—", "—", "직전값 유지"],
  ["지질 4종", "설명력 낮음", "—", "—", "참고용"],
], [2100, 2700, 1700, 1800, 1338], { compact: true });
figure(2, "수치 예측 정확도", "R2_accuracy.png", "연청은 직전 검진값 그대로, 진청은 예측 모델, 회색은 검진값의 자연 변동 때문에 더 내려가기 어려운 하한(추정)입니다. 공복혈당의 하한은 실제 변화가 섞여 높게 추정됐습니다.", 470, 268);
body("시간 순서 검증은 2025년 이전 검진으로 학습하고 이후 검진을 맞히는 방식입니다. 실제 서비스 상황과 같은 조건에서도 혈압 예측의 개선이 유지됐습니다.");

h1("3. 고위험 안내");
point(`고혈압 대상자 ${fv(HT)[RT].positives}명 중 ${fv(HT)[RT].positives - fv(HT)[RT].missed}명을 찾아냈습니다. 네 항목 모두 목표인 85%를 넘었습니다.`);
body(`수치 예측은 실제 고위험자의 값을 낮게 보는 경향이 있습니다. 이는 보정으로 고칠 수 있는 오류가 아니라 평균 회귀 현상이어서, 예측값 대신 '기준 초과 확률'로 안내 대상을 정했습니다. 일반적인 기준(확률 0.5 이상)으로는 고혈압 대상자 ${fv(HT)["rule_prob_ge_0.5"].positives}명 중 ${fv(HT)["rule_prob_ge_0.5"].missed}명을 놓치므로, '대상자의 85% 이상을 찾아낸다'는 규칙으로 기준점을 미리 정해 적용했습니다.`);
figure(3, "기준 초과자를 찾아낸 비율 — 안내 규칙별 비교", "R3_referral.png", "막대는 실제 기준 초과자 중 찾아낸 비율, 아래 숫자는 놓친 인원입니다. 진청이 적용한 안내 기준점입니다.", 500, 286);
table(["항목", "찾아낸 비율", "'낮음' 등급의 실제 초과율", "'주의' / '높음'의 실제 초과율", "안내 대상"], [
  ...[HT, "fasting_glucose_ge100", "obesity_bmi_ge25", "abdominal_obesity"].map((k, i) => { const v = fv(k), t = v.tiers, r = v[RT];
    return [["고혈압", "공복혈당장애", "비만", "복부비만"][i], `${pct(r.sensitivity)} (놓침 ${r.missed}/${r.positives})`, pct(t.low.actual_positive_rate), `${t.caution.n > 5 ? pct(t.caution.actual_positive_rate) : "—"} / ${pct(t.high.actual_positive_rate)}`, pct(r.flagged_rate)]; }),
], [1700, 2500, 2100, 2200, 1138], { compact: true });
callout("유의  ", `고혈압은 안내 대상이 ${pct(fv(HT)[RT].flagged_rate)}로 넓고 그중 실제 고혈압은 ${pct(fv(HT)[RT].ppv)}입니다. '주의'는 재측정 권유, '높음'만 병원 안내로 나누는 운영을 제안합니다. '낮음' 등급은 ${pct(1 - fv(HT).tiers.low.actual_positive_rate)}가 실제 정상입니다.`, C.amber, "D97706", false);

h1("4. 웨어러블 측정값 활용");
point("체중계 측정값은 예측을 개선했고 혈압계 측정값은 그렇지 않았습니다. 검진 이력 없는 사용자에게도 체중과 수축기혈압을 제공합니다.");
figure(4, "웨어러블 측정값의 효과 (평균 오차)", "R4_wearable.png", "왼쪽은 검진 이력이 있는 사용자, 오른쪽은 검진 이력이 없는 경우입니다. 막대 위 글씨가 채택 판정입니다.", 500, 286);
table(["대상", "항목", "오차 변화", "판정"], [
  hl(["검진 이력 있음", "체중 (BMI 파생)", `${fu.weight.with_prior_checkup.mae_base} → ${fu.weight.with_prior_checkup.mae_fused} kg`, "조건부 채택 (표본 추가 후 재평가)"], C.amber),
  ["검진 이력 있음", "수축기 / 이완기혈압", `${fu.sbp.with_prior_checkup.mae_base} → ${fu.sbp.with_prior_checkup.mae_fused} / ${fu.dbp.with_prior_checkup.mae_base} → ${fu.dbp.with_prior_checkup.mae_fused}`, "미채택 (개선 없음)"],
  hl(["검진 이력 없음", "체중", `성별·연령 평균 ${fu.weight.no_prior_checkup.mae_korean_reference_only} → ${fu.weight.no_prior_checkup.mae_m0_measured} kg`, "채택"], C.mint),
  hl(["검진 이력 없음", "수축기혈압", `${fu.sbp.no_prior_checkup.mae_korean_reference_only} → ${fu.sbp.no_prior_checkup.mae_m0_measured} mmHg`, "채택 (참고 표기)"], C.mint),
], [2000, 2300, 3100, 2238], { zebra: false, compact: true });
body(`혈압계 측정값이 도움이 되지 않은 이유는 측정 횟수가 적고(중앙 3회) 측정 자세·시간이 표준화돼 있지 않기 때문입니다. 그 밖에 방문 이력 통계와 다른 혈액 항목을 입력에 추가하는 방법도 시험했으나 개선이 최대 ${Math.max(ab.sbp.best_gain_pct, ab.dbp.best_gain_pct, ab.fasting_glucose.best_gain_pct)}%에 그쳐 채택하지 않았습니다.`);

h1("5. 항목별 활용 수준과 산출 범위", true);
point(`전체 ${rs.users}명에게 산출합니다. 혈압·혈당 예측과 고위험 안내는 의료진 검토용, 나머지는 참고용입니다.`);
table(["항목", "성능", "활용 수준"], [
  hl(["혈압 수치 (수축기 / 이완기)", `오차 ${sg.sbp.mae_model} / ${sg.dbp.mae_model} mmHg. 직전값보다 유의하게 정확`, "의료진 검토용"], C.mint),
  hl(["공복혈당 수치", `오차 ${sg.fasting_glucose.mae_model} mg/dL. 유의, 시간 순서 검증은 경계`, "의료진 검토용"], C.mint),
  hl(["고혈압·혈당장애·비만·복부비만 안내", `찾아낸 비율 ${pct(fv(HT)[RT].sensitivity)} / ${pct(fv("fasting_glucose_ge100")[RT].sensitivity)} / ${pct(fv("obesity_bmi_ge25")[RT].sensitivity)} / ${pct(fv("abdominal_obesity")[RT].sensitivity)}`, "의료진 검토용 (기준점 승인 필요)"], C.mint),
  hl(["체중·BMI", `체중계 측정값 반영. 오차 ${fu.weight.with_prior_checkup.mae_fused} kg`, "참고 표기"], C.amber),
  hl(["검진 이력 없는 사용자", `체중 오차 ${fu.weight.no_prior_checkup.mae_m0_measured} kg, 수축기 ${fu.sbp.no_prior_checkup.mae_m0_measured} mmHg`, "체중 사용 가능, 혈압 참고"], C.amber),
  ["지질 4종, 허리둘레", "설명력 낮음 또는 직전값 유지", "참고용"],
  hl(["걸음·심박·수면을 반영한 예측", `검증 데이터 ${fn.users_ge1d}명 < 30명`, "미검증"], C.rose),
], [3300, 4000, 2338], { zebra: false, compact: true });
figure(5, "항목별 산출 범위와 산출 방식", "R5_coverage.png", "연청은 검진 이력 기반 예측, 진청은 체중계 측정값 반영, 파랑은 검진 이력이 없거나 3년 넘게 오래된 사용자, 회색은 근거 부족으로 보류한 사용자입니다.", 500, 286);

h1("6. 제한사항과 보완 계획", true);
point("위 표는 현재로서는 풀 수 없는 제한, 아래 표는 데이터나 결정이 있으면 풀리는 과제입니다.");
table(["제한 (현재 해결 불가)", "이유", "풀리는 조건"], [
  hl(["걸음·심박·수면의 예측 기여 확인", `'착용 뒤 검진' 기록 ${fn.users_ge1d}명. 학습·검증 모두 불가`, "30명 이상 확보 (3~6개월)"], C.rose),
  hl(["수치 예측 정확도의 상한", `검진값 자체가 같은 사람도 ±${nc.sbp.sigma_within} mmHg 변동. 남은 여지 약 ${room}%`, "반복 측정으로 기준값의 변동을 줄여야 함"], C.rose),
  ["혈당·지질의 웨어러블 추정", "측정 채널 없음", "연속혈당측정기 등 기기 연동"],
  ["검진 이력 없는 사용자의 이완기·혈당·지질·BMI", "측정값 효과 없음 또는 키 정보 없음", "첫 검진 업로드, 프로필 키 수집"],
  ["검증 표본이 작음", `검증 61명, 고혈압 ${fv(HT)[RT].positives}명. 찾아낸 비율의 신뢰 구간 ${pct(fv(HT)[RT].sens_ci95[0])}~${pct(fv(HT)[RT].sens_ci95[1])}`, "사용자 증가"],
], [3100, 3800, 2738], { zebra: false, compact: true });
table(["보완 과제", "현재 상태", "보완 방법"], [
  ["고혈압 안내 대상이 넓음", `안내 ${pct(fv(HT)[RT].flagged_rate)}, 그중 실제 ${pct(fv(HT)[RT].ppv)}`, "'주의'는 재측정, '높음'만 병원 안내. 기준점 의료진 확정"],
  ["공복혈당 시간 순서 검증이 경계", "개선은 있으나 통계적 확정 전", "분기마다 재검증, 그 전에는 검토용 유지"],
  ["체중계 측정값 반영이 조건부 채택", "검증 쌍 70개", "100쌍 이상에서 재평가"],
  ["혈압계 측정 품질", "중앙 3회, 조건 비표준", "'아침 안정 시 2회' 측정 안내"],
  ["운영 자동화", "모델 갱신·산출이 수동", "주간 자동 갱신과 성능 추적"],
], [2900, 2700, 4038], { compact: true });
callout("다음 단계  ", "① 안내 기준점 의료진 승인  ② 검진 결과 업로드 캠페인('착용 뒤 검진' 30명)  ③ 가정 혈압 측정 안내  ④ 주간 자동 갱신. 모두 모델 기법이 아니라 데이터와 운영의 과제입니다.");
src("본 모델은 진단·치료가 아닌 검진·진료 안내 보조 도구입니다. 모든 수치는 가명 처리된 자체 데이터의 집계값이며 데이터 기준일은 2026-09-17입니다.");

const footer = new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TW }], children: [
  new TextRun({ text: "건강검진 예측 모델 결과 보고서 · 헬스커넥트(주) · 대외비", color: C.gray, size: 16 }), new TextRun({ text: "\t", color: C.gray, size: 16 }), new TextRun({ children: [PageNumber.CURRENT], color: C.gray, size: 16 })] })] });
const doc = new Document({
  styles: { default: { document: { run: { font: "Pretendard", color: C.text, size: 20 } } }, paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Pretendard", bold: true, color: C.navy, size: 28 }, paragraph: { outlineLevel: 0 } }] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "●", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } }, run: { color: C.gray, size: 12 } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134, header: 708, footer: 708 } } }, footers: { default: footer }, children: ch }],
});
Packer.toBuffer(doc).then(buf => { const out = "/Users/jaeho.oh/Downloads/SiBC_건강검진예측모델_결과보고서_20260918.docx"; fs.writeFileSync(out, buf); console.log("written", out, buf.length); });
