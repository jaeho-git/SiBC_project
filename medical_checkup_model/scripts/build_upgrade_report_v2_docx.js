// 고도화 결과 보고서 v2 — 경영진 보고용 간결판(2쪽 핵심 요약 + 본문 6장). 헬퍼는 v1과 동일 — 원본 주석: 모델 분석 보고서 v3 — v2(푸드렌즈 템플릿 포맷)에서 (1) 표 테두리를 표 단위로 통일(뷰어별 선 어긋남 방지), (2) '봉인' 등 전문 용어를 쉬운 말로 교체,
// (3) 보고서 구성표·장별 요점·그림 번호(1~6) 상호참조를 추가해 추적성을 높임. 실행: NODE_PATH=<docx 위치> node scripts/build_analysis_report_v3_docx.js
const fs = require("fs"), path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel, LevelFormat, ImageRun, Footer, PageNumber, TabStopType, VerticalAlign, TableLayoutType } = require("docx");
const ROOT = path.join(__dirname, ".."), ASSETS = path.join(__dirname, "upgrade_assets");
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

const sg = sig.m1, fu = m2.fusion, rf = m2.referral, tp = m2.temporal, nc = m2.noise_ceiling, cal = m2.calibration, ab = m2.history_ablation;
const wp = ds.wearable_prev, wn = ds.wearable_now, fp = ds.forward_prev_with_current_labels, fn = ds.forward_now, ln = ds.labels_now;
const pct = x => Math.round(x * 100) + "%";
const fv = k => rf[k].final_validation, RT = "rule_referral_threshold", HT = "hypertension_140_90";
const gain = k => Math.round((1 - sg[k].mae_model / sg[k].mae_cf) * 100);
const gateKo = { ADOPT: "채택", PROVISIONAL: "조건부 채택", REJECT: "미채택" };
const chg = (a, b) => `+${(b - a).toLocaleString()} (+${Math.round((b - a) / a * 100)}%)`;
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
ch.push(P([R("HEALTH CHECKUP PREDICTION MODEL — UPGRADE RESULT", { bold: true, color: C.blue, size: 24 })], { spacing: { after: 210 } }));
ch.push(P([R("건강검진 예측 모델 고도화 결과 보고서", { bold: true, size: 52 })], { spacing: { after: 110 } }));
ch.push(P([R("최신 데이터 재구축 · 고도화 적용 · 남은 한계", { size: 30 })], { spacing: { after: 5200 } }));
ch.push(P([R("오재호 과장", { bold: true, size: 26 })], { spacing: { after: 55 } }));
ch.push(P([R("AI플랫폼본부 SiBC · 2026-09-17", { color: C.gray })], { spacing: { after: 36 } }));

// ================= 핵심 요약 (1쪽) =================
ch.push(P([R("EXECUTIVE SUMMARY", { bold: true, color: C.blue, size: 24 })], { spacing: { before: 90, after: 80 }, pageBreakBefore: true }));
ch.push(P([R("핵심 요약", { bold: true, size: 32 })], { spacing: { after: 140 } }));
callout("결론  ", `혈압·혈당 예측과 고위험 안내는 의료진 검토용으로 쓸 수 있는 수준입니다. 이번 고도화로 고위험자 놓침을 크게 줄였고 산출 대상을 ${up.m2_users}명으로 넓혔습니다. 걸음·심박·수면의 효과는 검증용 데이터가 부족해 아직 확인할 수 없습니다.`);
ch.push(P([], { spacing: { after: 120 } }));
kpi([
  { label: "고혈압 놓침", value: `${fv(HT)["rule_prob_ge_0.5"].missed} → ${fv(HT)[RT].missed}명`, note: `실제 고혈압 ${fv(HT)[RT].positives}명 기준. 안내 기준점 재설정`, fill: C.mint, color: C.green },
  { label: "산출 대상 사용자", value: `${up.m1_users} → ${up.m2_users}명`, note: `검진 이력 없는 ${up.no_checkup_users}명 신규 포함` },
  { label: "혈압 예측 오차", value: `−${gain("sbp")}% · −${gain("dbp")}%`, note: "직전 검진값 대비 수축기 / 이완기. 통계적으로 유의" },
  { label: "간접 신호 검증용 정답지", value: `${fn.users_ge1d} / 30명`, note: "'착용 뒤 검진'. 기준 미달로 검증 불가", fill: C.rose, color: C.red },
]);
sub("결과 요약");
table(["구분", "결과", "판정"], [
  ["데이터", `이전 데이터셋 대비 웨어러블 ${wp.users}→${wn.users}명, 검진 394→${ln.users}명. 정답지는 ${fp.users_ge1d}→${fn.users_ge1d}명`, "증가, 병목 유지"],
  ["재구축", `혈압·혈당 예측 개선 유지(오차 −${gain("sbp")}% / −${gain("dbp")}% / −${gain("fasting_glucose")}%). 기준 초과 플래그 4종 모두 유의`, "결론 재현"],
  hl(["고도화 ① 안내 기준점", `고혈압 놓침 ${fv(HT)["rule_prob_ge_0.5"].missed}→${fv(HT)[RT].missed}명. 4개 문제 모두 찾아낸 비율 85% 이상. 낮음·주의·높음 3단계 제공`, "채택"], C.mint),
  hl(["고도화 ② 측정값 융합", `체중 오차 ${fu.weight.with_prior_checkup.mae_base}→${fu.weight.with_prior_checkup.mae_fused} kg. 검진 이력 없는 사용자에 체중·수축기혈압 신규 제공. 혈압계 측정값은 효과 없음`, "체중만 채택"], C.amber),
  ["고도화 ③ 시간 순서 검증", "과거로 학습해 이후 검진 평가. 혈압 통과, 공복혈당 경계", "혈압 통과"],
  hl(["한계", `수치 예측은 검진값 자체의 변동 때문에 남은 여지 최대 약 ${room}%. 걸음·심박·수면 효과는 정답지 30명 확보 전까지 확인 불가`, "데이터·시간 필요"], C.rose),
], [2100, 5900, 1638], { zebra: false });
sub("결정이 필요한 사항");
bullet("안내 기준점 승인.", `고혈압 놓침은 줄지만 사용자의 ${pct(fv(HT)[RT].flagged_rate)}가 '주의' 이상이 됩니다. 의료진과 기준 확정이 필요합니다.`);
bullet("검진 결과 업로드 캠페인.", "정답지 30명 확보가 웨어러블 효과 검증의 유일한 경로입니다. 3~6개월이 걸립니다.");
bullet("가정 혈압 측정 안내.", "측정 횟수와 조건이 표준화되어야 혈압계 데이터를 모델에 쓸 수 있습니다.");

// ================= 본문 =================
h1("1. 데이터 현황", true);
point(`모든 항목이 3~12% 늘었습니다. 간접 신호 검증에 필요한 정답지만 ${fn.users_ge1d}명으로 기준 30명에 못 미칩니다.`);
table(["구분", "이전 데이터셋 (직전 모델 학습분)", "현재 데이터셋 (9/17 조회)", "변동"], [
  ["웨어러블 사용자", `${wp.users}명`, `${wn.users}명`, chg(wp.users, wn.users)],
  ["웨어러블 기록 일수", `${wp.user_days.toLocaleString()}일`, `${wn.user_days.toLocaleString()}일`, chg(wp.user_days, wn.user_days)],
  ["혈압 / 체중 측정 사용자", `${wp.by_feature.bp_systolic_measured.users} / ${wp.by_feature.body_weight_measured.users}명`, `${wn.by_feature.bp_systolic_measured.users} / ${wn.by_feature.body_weight_measured.users}명`, `+${wn.by_feature.bp_systolic_measured.users - wp.by_feature.bp_systolic_measured.users} / +${wn.by_feature.body_weight_measured.users - wp.by_feature.body_weight_measured.users}명`],
  ["검진 보유 사용자 / 건수", "394명 / 1,549건", `${ln.users}명 / ${ln.events.toLocaleString()}건`, `${chg(394, ln.users)} / ${chg(1549, ln.events)}`],
  hl(["'착용 뒤 검진' 정답지", `${fp.users_ge1d}명`, `${fn.users_ge1d}명`, "+2명, 기준 30명 미달"], C.rose),
], [3000, 2100, 2300, 2238], { zebra: false, compact: true });
figure(1, "이전 대비 현재 데이터셋의 변동", "U1_data.png", "왼쪽은 사용자 수와 변동률, 오른쪽은 정답지와 검증 시작 기준 30명의 간격입니다.", 480, 274);
body("직전 모델이 쓴 웨어러블 입력: 서비스용 개인화 모델·플래그는 0개, 통합 모델만 걸음·활동량·활동 시간·악력 4종. 가장 많이 쌓인 혈압계·체중계 측정값은 쓰이지 않아 이번에 반영했습니다.");

h1("2. 재구축 결과");
point("학습에 쓰지 않은 사용자 61명으로 검증했습니다. 결론이 유지됐고, 플래그는 4종 모두 개선이 유의해졌습니다.");
table(["항목", "이전 모델", "재구축 모델", "판정"], [
  ["수축기혈압 오차 (직전값 → 모델)", `${old.m1.sbp.mae_cf} → ${old.m1.sbp.mae_model}`, `${sg.sbp.mae_cf} → ${sg.sbp.mae_model}`, "유의, 유지"],
  ["이완기혈압 오차", `${old.m1.dbp.mae_cf} → ${old.m1.dbp.mae_model}`, `${sg.dbp.mae_cf} → ${sg.dbp.mae_model}`, "유의, 유지"],
  ["공복혈당 오차", `${old.m1.fasting_glucose.mae_cf} → ${old.m1.fasting_glucose.mae_model}`, `${sg.fasting_glucose.mae_cf} → ${sg.fasting_glucose.mae_model}`, "유의, 유지"],
  ["고혈압 / 혈당장애 판별력 (0.8 이상 양호, 0.9 이상 우수)", `${old.clf.hypertension_140_90.auroc} / ${old.clf.fasting_glucose_ge100.auroc}`, `${sig.clf.hypertension_140_90.auroc} / ${sig.clf.fasting_glucose_ge100.auroc}`, "유의로 전환"],
  ["비만 / 복부비만 판별력", `${old.clf.obesity_bmi_ge25.auroc} / ${old.clf.abdominal_obesity.auroc}`, `${sig.clf.obesity_bmi_ge25.auroc} / ${sig.clf.abdominal_obesity.auroc}`, "유의 유지"],
  ["체중·BMI·허리둘레", "직전값 유지", "직전값 유지", "동일"],
], [3400, 2000, 2200, 2038], { compact: true });

h1("3. 고도화 ① 안내 기준점 — 고위험자를 놓치지 않기");
point(`기존 플래그는 고혈압 ${fv(HT)[RT].positives}명 중 ${fv(HT)["rule_prob_ge_0.5"].missed}명을 놓쳤습니다. 기준점을 다시 정해 ${fv(HT)[RT].missed}명으로 줄였습니다.`);
body("고위험 구간에서 값이 낮게 예측되는 현상은 보정으로 고칠 수 있는 편향이 아니라 평균 회귀였습니다. 그래서 값을 올리는 대신 '누구를 안내할지'의 기준을 바꿨습니다. 기준점은 결과를 보기 전에 '기준 초과자의 85% 이상을 찾아낸다'는 규칙으로 고정했습니다.");
figure(2, "고위험자를 찾아낸 비율 — 안내 규칙별 비교", "U3_referral.png", "막대는 실제 기준 초과자 중 찾아낸 비율, 아래 숫자는 놓친 인원입니다. 진청이 새 기준점입니다.", 560, 320);
table(["문제", "찾아낸 비율", "'낮음' 등급의 실제 초과율", "'주의' / '높음'의 실제 초과율", "안내 대상"], [
  ...[HT, "fasting_glucose_ge100", "obesity_bmi_ge25", "abdominal_obesity"].map((k, i) => { const v = fv(k), t = v.tiers, r = v[RT];
    return [["고혈압", "공복혈당장애", "비만", "복부비만"][i], `${pct(r.sensitivity)} (놓침 ${r.missed}/${r.positives})`, pct(t.low.actual_positive_rate), `${t.caution.n > 5 ? pct(t.caution.actual_positive_rate) : "—"} / ${pct(t.high.actual_positive_rate)}`, pct(r.flagged_rate)]; }),
], [1700, 2500, 2100, 2200, 1138], { compact: true });
callout("유의  ", `고혈압은 안내 대상이 ${pct(fv(HT)[RT].flagged_rate)}로 넓고 그중 실제 고혈압은 ${pct(fv(HT)[RT].ppv)}입니다. '주의'는 재측정 권유, '높음'만 병원 안내로 나누는 운영을 제안합니다. '낮음' 등급은 ${pct(1 - fv(HT).tiers.low.actual_positive_rate)}가 실제 정상입니다.`, C.amber, "D97706", false);

h1("4. 고도화 ② 웨어러블 측정값 융합", true);
point("체중은 정확해졌고 혈압은 그렇지 않았습니다. 검진 이력 없는 사용자에게 새 산출 경로가 생겼습니다.");
figure(3, "측정값 융합의 효과 (평균 오차)", "U4_fusion.png", "왼쪽은 직전 검진이 있는 사용자, 오른쪽은 검진 이력이 없는 경우입니다. 막대 위 글씨가 채택 판정입니다.", 560, 320);
table(["대상", "항목", "오차 변화", "판정"], [
  hl(["직전 검진 보유", "체중 (BMI 파생)", `${fu.weight.with_prior_checkup.mae_base} → ${fu.weight.with_prior_checkup.mae_fused} kg`, "조건부 채택 (표본 추가 후 재평가)"], C.amber),
  ["직전 검진 보유", "수축기 / 이완기혈압", `${fu.sbp.with_prior_checkup.mae_base} → ${fu.sbp.with_prior_checkup.mae_fused} / ${fu.dbp.with_prior_checkup.mae_base} → ${fu.dbp.with_prior_checkup.mae_fused}`, "미채택 (개선 없음)"],
  hl(["검진 이력 없음", "체중", `성별·연령 평균 ${fu.weight.no_prior_checkup.mae_korean_reference_only} → ${fu.weight.no_prior_checkup.mae_m0_measured} kg`, "채택"], C.mint),
  hl(["검진 이력 없음", "수축기혈압", `${fu.sbp.no_prior_checkup.mae_korean_reference_only} → ${fu.sbp.no_prior_checkup.mae_m0_measured} mmHg`, "채택 (참고 표기)"], C.mint),
], [2000, 2300, 3100, 2238], { zebra: false, compact: true });
body("혈압계 측정값이 도움이 되지 않은 이유는 측정 횟수가 적고(중앙 3회) 측정 자세·시간이 표준화돼 있지 않기 때문입니다.");
sub("시간 순서 검증과 채택하지 않은 시도");
table(["구분", "결과", "판정"], [
  ["시간 순서 검증: 수축기 / 이완기혈압", `오차 −${tp.sbp.improve_pct}% / −${tp.dbp.improve_pct}%, 유의`, "통과"],
  ["시간 순서 검증: 공복혈당", `오차 −${tp.fasting_glucose.improve_pct}%, 구간이 0에 걸침`, "경계"],
  ["방문 이력·다른 혈액 항목을 입력에 추가", `개선 최대 ${Math.max(ab.sbp.best_gain_pct, ab.dbp.best_gain_pct, ab.fasting_glucose.best_gain_pct)}%`, "미채택 (기준 3% 미달)"],
  ["예측값 재보정으로 고위험 과소예측 교정", "편향 변화 없음", "미채택"],
], [4300, 3300, 2038], { compact: true });

h1("5. 고도화 모델 성능 요약");
point(`산출 대상이 ${up.m1_users}명에서 ${up.m2_users}명으로 늘었습니다. 항목별 사용 수준은 아래와 같습니다.`);
table(["항목", "성능", "사용 수준"], [
  hl(["혈압 수치 (수축기 / 이완기)", `오차 ${sg.sbp.mae_model} / ${sg.dbp.mae_model} mmHg. 직전값보다 유의하게 정확`, "의료진 검토용"], C.mint),
  hl(["공복혈당 수치", `오차 ${sg.fasting_glucose.mae_model} mg/dL. 유의, 시간 순서 검증은 경계`, "의료진 검토용"], C.mint),
  hl(["고혈압·혈당장애·비만·복부비만 안내", `찾아낸 비율 ${pct(fv(HT)[RT].sensitivity)} / ${pct(fv("fasting_glucose_ge100")[RT].sensitivity)} / ${pct(fv("obesity_bmi_ge25")[RT].sensitivity)} / ${pct(fv("abdominal_obesity")[RT].sensitivity)}`, "의료진 검토용 (기준점 승인 필요)"], C.mint),
  hl(["체중·BMI", `웨어러블 체중 융합. 오차 ${fu.weight.with_prior_checkup.mae_fused} kg`, "참고 표기"], C.amber),
  hl(["검진 이력 없는 사용자", `체중 오차 ${fu.weight.no_prior_checkup.mae_m0_measured} kg, 수축기 ${fu.sbp.no_prior_checkup.mae_m0_measured} mmHg`, "체중 사용 가능, 혈압 참고"], C.amber),
  ["지질 4항목, 허리둘레", "변화 없음", "참고용"],
  hl(["걸음·심박·수면 반영 예측", `정답지 ${fn.users_ge1d}명 < 30명`, "미검증"], C.rose),
], [3300, 4000, 2338], { zebra: false, compact: true });
figure(4, "서비스 산출 범위 — 고도화 전과 후", "U5_coverage.png", "진청은 측정값 융합, 파랑은 검진 이력이 없거나 오래돼 기존에는 보류되던 사용자입니다.", 560, 320);

h1("6. 문제점·보완과 제한사항", true);
point("위 표는 데이터나 결정이 있으면 풀리는 문제, 아래 표는 현재로서는 풀 수 없는 제한입니다.");
table(["문제점", "근거", "보완 방법"], [
  ["고혈압 안내 대상이 넓음", `안내 ${pct(fv(HT)[RT].flagged_rate)}, 그중 실제 ${pct(fv(HT)[RT].ppv)}`, "'주의'는 재측정, '높음'만 병원 안내. 기준점 의료진 확정"],
  ["공복혈당 시간 순서 검증 경계", `개선 구간 [${tp.fasting_glucose.diff_ci95}]`, "분기마다 재검증, 그 전에는 검토용 유지"],
  ["체중 융합 조건부 채택", "검증 쌍 70개", "100쌍 이상에서 재평가"],
  ["혈압계 측정 품질", "중앙 3회, 조건 비표준", "'아침 안정 시 2회' 측정 안내"],
  ["운영 자동화 없음", "재구축·산출 수동", "주간 재구축과 성능 추적 자동화"],
], [2900, 2700, 4038], { compact: true });
table(["제한 (현재 해결 불가)", "이유", "풀리는 조건"], [
  hl(["걸음·심박·수면의 예측 기여 확인", `정답지 ${fn.users_ge1d}명. 학습·검증 모두 불가`, "정답지 30명 이상 (3~6개월)"], C.rose),
  hl(["수치 예측 정확도의 상한", `검진값 자체가 같은 사람도 ±${nc.sbp.sigma_within} mmHg 변동. 남은 여지 약 ${room}%`, "반복 측정으로 기준값의 변동을 줄여야 함"], C.rose),
  ["혈당·지질의 웨어러블 추정", "측정 채널 없음", "연속혈당측정기 등 기기 연동"],
  ["이력 없는 사용자의 이완기·혈당·지질·BMI", "측정값 효과 없음 또는 키 정보 없음", "첫 검진 업로드, 프로필 키 수집"],
  ["검증 표본이 작음", `검증 61명, 고혈압 ${fv(HT)[RT].positives}건. 찾아낸 비율 구간 ${pct(fv(HT)[RT].sens_ci95[0])}~${pct(fv(HT)[RT].sens_ci95[1])}`, "사용자 증가"],
], [3100, 3800, 2738], { zebra: false, compact: true });
callout("다음 단계  ", "① 안내 기준점 의료진 승인  ② 검진 결과 업로드 캠페인(정답지 30명)  ③ 가정 혈압 측정 안내  ④ 주간 재구축 자동화. 모두 모델 기법이 아니라 데이터와 운영의 과제입니다.");
src("근거: 01_Results/data_status_2026-09-17.json · m2/m2_report.json · significance.json (가명키, 집계값). 본 모델은 진단·치료가 아닌 검진·진료 안내 보조 도구입니다.");

const footer = new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TW }], children: [
  new TextRun({ text: "건강검진 예측 모델 고도화 결과 보고서 · 헬스커넥트(주) · 대외비", color: C.gray, size: 16 }), new TextRun({ text: "\t", color: C.gray, size: 16 }), new TextRun({ children: [PageNumber.CURRENT], color: C.gray, size: 16 })] })] });
const doc = new Document({
  styles: { default: { document: { run: { font: "Pretendard", color: C.text, size: 20 } } }, paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Pretendard", bold: true, color: C.navy, size: 28 }, paragraph: { outlineLevel: 0 } }] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "●", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } }, run: { color: C.gray, size: 12 } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134, header: 708, footer: 708 } } }, footers: { default: footer }, children: ch }],
});
Packer.toBuffer(doc).then(buf => { const out = "/Users/jaeho.oh/Downloads/SiBC_건강검진예측모델_고도화결과보고서_20260917.docx"; fs.writeFileSync(out, buf); console.log("written", out, buf.length); });
