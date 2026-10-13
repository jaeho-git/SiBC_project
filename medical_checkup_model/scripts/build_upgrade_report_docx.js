// 고도화 결과 보고서 (분석 보고서 v3와 같은 템플릿·헬퍼) — 원본 주석: 모델 분석 보고서 v3 — v2(푸드렌즈 템플릿 포맷)에서 (1) 표 테두리를 표 단위로 통일(뷰어별 선 어긋남 방지), (2) '봉인' 등 전문 용어를 쉬운 말로 교체,
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
const HO = "최종 검증";
const sg = sig.m1, fu = m2.fusion, rf = m2.referral, tp = m2.temporal, nc = m2.noise_ceiling, cal = m2.calibration, ab = m2.history_ablation;
const wp = ds.wearable_prev, wn = ds.wearable_now, fp = ds.forward_prev_with_current_labels, fn = ds.forward_now, ln = ds.labels_now;
const pct = x => Math.round(x * 100) + "%";
const fv = k => rf[k].final_validation, RT = "rule_referral_threshold";
const gateKo = { ADOPT: "채택", PROVISIONAL: "조건부 채택", REJECT: "미채택" };

// ================= 표지 =================
ch.push(P([R("헬스커넥트(주) · AI플랫폼본부 SiBC", { bold: true, size: 22 })], { spacing: { after: 55 } }));
ch.push(P([R("대외비 · CONFIDENTIAL", { bold: true, color: C.red, size: 18 })], { spacing: { after: 1450 } }));
ch.push(P([R("HEALTH CHECKUP PREDICTION MODEL — UPGRADE RESULT", { bold: true, color: C.blue, size: 24 })], { spacing: { after: 210 } }));
ch.push(P([R("건강검진 예측 모델 고도화 결과 보고서", { bold: true, size: 52 })], { spacing: { after: 110 } }));
ch.push(P([R("최신 데이터 재구축, 고도화 적용, 그리고 남은 한계", { size: 30 })], { spacing: { after: 300 } }));
ch.push(P([R("2026-09-17 기준 데이터로 모델을 다시 만들고, 현실적으로 검증 가능한 고도화를 적용한 뒤,", { size: 22 })], { spacing: { after: 40 } }));
ch.push(P([R("성능·문제점·보완 사항·현재로서는 해결할 수 없는 제한을 처음 보는 분도 따라갈 수 있게 정리했습니다.", { size: 22 })], { spacing: { after: 4200 } }));
ch.push(P([R("오재호 과장", { bold: true, size: 26 })], { spacing: { after: 55 } }));
ch.push(P([R("AI플랫폼본부 SiBC", { color: C.gray })], { spacing: { after: 36 } }));

// ================= EXECUTIVE SUMMARY =================
ch.push(P([R("EXECUTIVE SUMMARY", { bold: true, color: C.blue, size: 24 })], { spacing: { before: 90, after: 80 }, pageBreakBefore: true }));
ch.push(P([R("결론", { bold: true, size: 32 })], { spacing: { after: 120 } }));
bullet("데이터는 늘었지만 병목은 그대로입니다.", `직전 모델을 만들 때 쓴 이전 데이터셋과 비교하면, 현재(2026-09-17 기준) 데이터셋은 웨어러블 사용자 ${wp.users}→${wn.users}명, 검진 보유 394→${ln.users}명으로 늘었습니다. 그러나 걸음·심박·수면 같은 간접 신호를 검증할 '착용 뒤 검진' 정답지는 ${fp.users_ge1d}→${fn.users_ge1d}명으로 여전히 기준 30명의 절반입니다. → 1~2장, 그림 1`);
bullet("재구축 결과는 기존 결론을 재현했습니다.", `혈압·공복혈당 개인화 예측은 새 ${HO}에서도 직전값보다 유의하게 정확했고, 기준 초과 플래그 4종은 이번에 모두 기준선 대비 개선이 유의해졌습니다. → 3장`);
bullet("가장 큰 고도화는 '안내 기준점'입니다.", `기존 고혈압 플래그(확률 0.5 이상)는 실제 고혈압 ${fv("hypertension_140_90")["rule_prob_ge_0.5"].positives}명 중 ${fv("hypertension_140_90")["rule_prob_ge_0.5"].missed}명을 놓쳤습니다. 기준점을 사전 규칙(민감도 85% 목표)으로 다시 정하자 놓침이 ${fv("hypertension_140_90")[RT].missed}명으로 줄었습니다. 고위험 과소예측은 값을 끌어올려 고칠 수 있는 편향이 아니라 평균 회귀 현상임도 확인했습니다. → 4~5장, 그림 2·3`);
bullet("웨어러블 측정값 융합은 체중에서만 효과가 있었습니다.", `체중은 오차 ${fu.weight.with_prior_checkup.mae_base}→${fu.weight.with_prior_checkup.mae_fused} kg(조건부 채택)이고, 검진 이력이 없는 사용자에게도 체중(오차 ${fu.weight.no_prior_checkup.mae_m0_measured} kg)과 참고용 수축기혈압을 새로 제공합니다. 웨어러블 혈압계 측정값은 기존 예측에 더해도 정확도가 오르지 않았습니다. → 6장, 그림 4`);
callout("시사점: ", `이번 고도화로 '고위험자를 놓치지 않는 안내'와 '검진 이력 없는 사용자 ${up.no_checkup_users}명에 대한 산출'이 추가됐습니다. 수치 예측의 정확도 자체는 검진값의 자연 변동 때문에 남은 여지가 크지 않으며(혈압 최대 약 16%), 간접 웨어러블 신호의 기여는 정답지가 30명에 도달해야 검증할 수 있습니다.`);
src(`자체 데이터 2026-09-17 조회(읽기 전용), 모델 v1.4·m1_v4·m2_v1, ${HO} 사용자 61명, 사용자 단위 부트스트랩 2,000회. 사용자 식별 정보는 사용하지 않았습니다.`);
ch.push(P([R("보고서 구성 — 어디서 무엇을 확인하는가", { bold: true, size: 24 })], { spacing: { before: 200, after: 100 }, keepNext: true }));
table(["PART", "장", "답하는 질문", "근거 그림"], [
  ["I. 데이터와 재구축", "1. 모델이 쓴 웨어러블 데이터", "최신 모델이 실제로 사용한 웨어러블 입력은 무엇인가", "—"],
  ["", "2. 누적 데이터 현황", "이전 데이터셋 대비 무엇이 얼마나 변했는가", "그림 1"],
  ["", "3. 재구축 결과", "최신 데이터로 다시 만들면 결론이 유지되는가", "—"],
  ["II. 고도화", "4. 성능을 막는 원인 진단", "왜 더 안 오르는가, 고위험 과소예측은 고칠 수 있는가", "그림 2"],
  ["", "5. 고도화 ① 안내 기준점", "고위험자를 얼마나 덜 놓치게 됐는가", "그림 3"],
  ["", "6. 고도화 ② 측정값 융합", "웨어러블 측정값을 더하면 정확해지는가", "그림 4"],
  ["", "7. 고도화 ③ 시간 순서 검증·미채택 실험", "미래 예측에서도 유지되는가, 무엇이 효과 없었나", "—"],
  ["III. 재분석", "8. 고도화 모델 성능 요약", "항목별로 지금 어디까지 써도 되는가", "그림 5"],
  ["", "9. 문제점과 보완 사항", "무엇이 아직 약하고 어떻게 보완하는가", "—"],
  ["", "10. 제한사항", "현재로서는 해결할 수 없는 것은 무엇인가", "—"],
], [2100, 2900, 3438, 1200], { zebra: false, compact: true });

// ================= PART I =================
partHead("PART I", "데이터와 재구축", "최신 모델이 쓴 웨어러블 데이터, 이전 데이터셋 대비 현재 데이터셋의 변동, 재구축 결과입니다.");
h1("1. 최신 모델이 실제로 사용한 웨어러블 데이터");
point("서비스용 개인화 모델(M1)은 웨어러블 입력이 0개였고, 통합 모델만 걸음·활동 계열 4종을 썼습니다. 혈압·체중 측정값은 어느 모델에도 입력으로 쓰이지 않았습니다.");
table(["모델", "역할", "사용한 웨어러블 입력", "쓰지 못한 이유"], [
  ["개인화 M1 (m1_v3→v4)", "검진 이력 보유자의 다음 검진값 예측. 현재 서비스 경로", "0개 (직전 검진값·경과일·추세·성별·연령만)", "검진 전에 웨어러블이 있는 학습 예시가 전체의 약 1%라 결측 95% 초과 입력 자동 제외"],
  ["통합 모델 (v1.3→v1.4)", "공공+자체 통합 학습. 이력 없는 사용자용 후보", "걸음 수, 활동량 백분위, 활동 시간, 악력", "심박·수면·산소포화도는 공공데이터에 대응 항목이 없어 자체 행에서만 존재 → 같은 이유로 제외"],
  ["기준 초과 플래그", "고혈압·혈당장애·비만·복부비만 판별", "0개", "M1과 같은 입력 사용"],
], [1900, 2500, 2500, 2738]);
body(`수집 중인 웨어러블 항목은 걸음, 심박 7종(안정·야간·변동성 등), 수면, 산소포화도, 악력, 그리고 기기로 직접 잰 혈압·체중입니다. 이 가운데 혈압(${wn.by_feature.bp_systolic_measured.users}명)과 체중(${wn.by_feature.body_weight_measured.users}명) 측정값이 가장 널리 쌓여 있는데도 모델 입력으로는 쓰이지 않고 화면 표시용으로만 나가고 있었습니다. 이번 고도화는 이 지점을 겨냥했습니다.`);
h1("2. 누적 데이터 현황 — 이전 데이터셋 대비 현재(9/17 기준) 변동");
point("현재 데이터셋은 전 항목이 3~12% 늘었지만, 간접 신호 검증에 필요한 '착용 뒤 검진'은 2명 증가에 그쳤습니다.");
body("'이전'은 직전 모델(v1.3·m1_v3)이 학습한 데이터셋, '현재'는 2026-09-17에 운영 DB에서 새로 조회한 데이터셋입니다. 두 열의 차이는 특정 기간의 증가량이 아니라 '모델이 알던 데이터'와 '지금 실제로 쌓여 있는 데이터'의 차이입니다.");
const chg = (a, b) => `+${(b - a).toLocaleString()} (+${Math.round((b - a) / a * 100)}%)`;
table(["구분", "이전 데이터셋", "현재 데이터셋 (9/17 기준)", "변동"], [
  ["웨어러블 사용자", `${wp.users}명`, `${wn.users}명`, chg(wp.users, wn.users)],
  ["웨어러블 기록 일수 (사용자×일)", `${wp.user_days.toLocaleString()}일`, `${wn.user_days.toLocaleString()}일`, chg(wp.user_days, wn.user_days)],
  ["30일 이상 착용자", `${wp.users_ge30days}명`, `${wn.users_ge30days}명`, chg(wp.users_ge30days, wn.users_ge30days)],
  ["혈압 측정 사용자", `${wp.by_feature.bp_systolic_measured.users}명`, `${wn.by_feature.bp_systolic_measured.users}명`, chg(wp.by_feature.bp_systolic_measured.users, wn.by_feature.bp_systolic_measured.users)],
  ["체중 측정 사용자", `${wp.by_feature.body_weight_measured.users}명`, `${wn.by_feature.body_weight_measured.users}명`, chg(wp.by_feature.body_weight_measured.users, wn.by_feature.body_weight_measured.users)],
  ["검진 보유 사용자", "394명", `${ln.users}명`, chg(394, ln.users)],
  ["검진 건수", "1,549건", `${ln.events.toLocaleString()}건`, chg(1549, ln.events)],
  hl(["'착용 뒤 검진' 정답지 (검진 전 90일 안에 웨어러블 기록)", `${fp.users_ge1d}명 / ${fp.pairs_ge1d}건`, `${fn.users_ge1d}명 / ${fn.pairs_ge1d}건`, `+${fn.users_ge1d - fp.users_ge1d}명 — 기준 30명 미달`], C.rose),
], [3700, 1800, 2300, 1838], { zebra: false, compact: true });
figure(1, "이전 대비 현재 데이터셋의 변동과 그대로인 병목", "U1_data.png", "왼쪽은 이전 데이터셋(연청)과 현재 데이터셋(진청)의 사용자 수와 변동률. 오른쪽은 간접 신호 검증에 필요한 정답지가 기준 30명에 얼마나 못 미치는지 보여 줍니다.", 600, 343);
h1("3. 재구축 결과 — 결론이 유지되는가");
point("새 사용자 26명이 들어가 검증 대상이 바뀌었는데도 혈압·혈당의 개선은 유의했고, 플래그 4종은 모두 개선이 유의해졌습니다.");
table(["항목", "이전 모델 (이전 데이터셋, 검증 59명)", "재구축 모델 (현재 데이터셋, 검증 61명)", "판정"], [
  ["수축기혈압 오차: 직전값 → 모델", `${old.m1.sbp.mae_cf} → ${old.m1.sbp.mae_model}`, `${sg.sbp.mae_cf} → ${sg.sbp.mae_model}  (개선 ${sg.sbp.diff} [${sg.sbp.diff_ci95}])`, "유의, 유지"],
  ["이완기혈압", `${old.m1.dbp.mae_cf} → ${old.m1.dbp.mae_model}`, `${sg.dbp.mae_cf} → ${sg.dbp.mae_model}  (개선 ${sg.dbp.diff} [${sg.dbp.diff_ci95}])`, "유의, 유지"],
  ["공복혈당", `${old.m1.fasting_glucose.mae_cf} → ${old.m1.fasting_glucose.mae_model}`, `${sg.fasting_glucose.mae_cf} → ${sg.fasting_glucose.mae_model}  (개선 ${sg.fasting_glucose.diff} [${sg.fasting_glucose.diff_ci95}])`, "유의, 유지"],
  ["고혈압 판별력(AUROC)", `${old.clf.hypertension_140_90.auroc} (개선 미확정)`, `${sig.clf.hypertension_140_90.auroc} (개선 ${sig.clf.hypertension_140_90.diff_vs_prior} [${sig.clf.hypertension_140_90.diff_ci95}])`, "유의로 전환"],
  ["공복혈당장애 판별력", `${old.clf.fasting_glucose_ge100.auroc} (경계)`, `${sig.clf.fasting_glucose_ge100.auroc} (개선 ${sig.clf.fasting_glucose_ge100.diff_vs_prior} [${sig.clf.fasting_glucose_ge100.diff_ci95}])`, "유의로 전환"],
  ["비만 / 복부비만 판별력", `${old.clf.obesity_bmi_ge25.auroc} / ${old.clf.abdominal_obesity.auroc}`, `${sig.clf.obesity_bmi_ge25.auroc} / ${sig.clf.abdominal_obesity.auroc}`, "유의 유지 (복부비만 소폭 하락)"],
  ["체중·BMI·허리둘레", "직전값 유지", "직전값 유지 (모델 개선 3% 미달)", "동일"],
], [2500, 2200, 3438, 1500]);

// ================= PART II =================
partHead("PART II", "고도화", "성능을 막는 원인을 먼저 진단하고, 검증 가능한 세 가지를 적용했습니다. 효과가 없던 시도도 함께 기록합니다.");
h1("4. 성능을 막는 원인 진단");
point("검진값 자체가 같은 사람에게서도 흔들리기 때문에 오차에는 바닥이 있습니다. 고위험 과소예측은 값을 보정해 고칠 수 있는 편향이 아닙니다.");
body(`같은 사람의 연속 검진 차이로 개인 내 변동을 추정하면 수축기혈압은 표준편차 ${nc.sbp.sigma_within} mmHg입니다. 개인의 참 수준을 완벽히 알아도 평균 오차는 약 ${nc.sbp.mae_floor_estimate} mmHg 밑으로 내려가기 어렵습니다. 현재 모델은 ${sg.sbp.mae_model}이므로 남은 여지는 최대 ${Math.round((1 - nc.sbp.mae_floor_estimate / sg.sbp.mae_model) * 100)}% 정도입니다.`);
figure(2, "남은 개선 여지", "U2_floor.png", "연청은 직전값 그대로, 진청은 우리 모델, 회색은 검진값의 자연 변동이 허용하는 오차 하한(추정). 진청과 회색의 간격이 앞으로 줄일 수 있는 최대폭입니다. 공복혈당은 하한 추정에 실제 변화가 섞여 모델보다 높게 나왔습니다.", 600, 343);
table(["진단", "결과", "해석"], [
  ["예측값 기준 보정 상태 (실제값 ~ 예측값 기울기)", `수축기 ${cal.sbp.slope_y_on_pred}, 이완기 ${cal.dbp.slope_y_on_pred}, 혈당 ${cal.fasting_glucose.slope_y_on_pred}`, "1에 가까움. 높게 예측한 사람은 실제로도 높음"],
  ["예측 상위 10% 구간의 실제 − 예측", `수축기 ${cal.sbp.top_decile_pred.gap_actual_minus_pred}, 이완기 ${cal.dbp.top_decile_pred.gap_actual_minus_pred}, 혈당 +${cal.fasting_glucose.top_decile_pred.gap_actual_minus_pred}`, "차이가 작음. 고칠 편향이 거의 없음"],
  ["기울기 재보정을 적용했을 때 고위험 구간 편향", `수축기 ${cal.sbp.actual_high.bias_pred_minus_actual} → ${cal.sbp.linear_recalibration.high_bias_after}`, "개선 없음. '실제 고위험자'만 골라 보면 어떤 예측도 낮게 보이는 평균 회귀 현상"],
], [3300, 3100, 3238]);
callout("결론: ", "고위험자 문제는 예측값을 끌어올려서가 아니라 '누구를 안내할지 정하는 규칙'으로 풀어야 합니다. 이것이 5장의 고도화입니다.", C.amber, "D97706", false);
h1("5. 고도화 ① 안내 기준점 — 고위험자를 놓치지 않기");
point("기존 플래그는 확률 0.5를 넘어야 켜졌는데, 고혈압처럼 드문 사건에서는 거의 켜지지 않았습니다. 기준점을 사전 규칙으로 다시 정했습니다.");
body(`규칙은 결과를 보기 전에 고정했습니다. 학습 사용자 안에서 교차검증한 확률로 '기준 초과자의 85% 이상을 찾아내는 가장 높은 기준점'을 고르고, ${HO} 사용자에게 한 번만 적용했습니다. 결과 화면은 낮음·주의·높음 3단계로 제공합니다.`);
figure(3, "고위험자 놓침 — 안내 규칙별 비교", "U3_referral.png", "막대 높이는 실제 기준 초과자 중 찾아낸 비율, 아래 숫자는 놓친 인원/전체입니다. 진청(새 기준점)이 네 문제 모두에서 목표 85%를 넘었습니다.", 600, 343);
table(["문제", "새 기준점", "찾아낸 비율 (95% 구간)", "'낮음' 등급의 실제 초과율", "'주의' / '높음' 등급의 실제 초과율", "안내 대상 비율"], [
  ...["hypertension_140_90", "fasting_glucose_ge100", "obesity_bmi_ge25", "abdominal_obesity"].map((k, i) => {
    const v = fv(k), t = v.tiers, r = v[RT];
    return [["고혈압 ≥140/90", "공복혈당장애 ≥100", "비만 BMI≥25", "복부비만"][i], `${rf[k].referral_threshold}`, `${pct(r.sensitivity)} [${pct(r.sens_ci95[0])}~${pct(r.sens_ci95[1])}]`, `${pct(t.low.actual_positive_rate)} (${t.low.n}건)`, `${t.caution.n ? pct(t.caution.actual_positive_rate) : "—"} / ${pct(t.high.actual_positive_rate)}`, pct(r.flagged_rate)];
  }),
], [1700, 1100, 2100, 1700, 1900, 1138]);
body(`대가도 분명합니다. 고혈압은 놓침을 ${fv("hypertension_140_90")["rule_prob_ge_0.5"].missed}명에서 ${fv("hypertension_140_90")[RT].missed}명으로 줄이는 대신 사용자의 ${pct(fv("hypertension_140_90")[RT].flagged_rate)}가 '주의' 이상으로 분류되고, 그중 실제 고혈압은 ${pct(fv("hypertension_140_90")[RT].ppv)}입니다. 반대로 '낮음' 등급은 ${pct(1 - fv("hypertension_140_90").tiers.low.actual_positive_rate)}가 실제로 정상이어서 '안심 안내'에는 신뢰할 수 있습니다.`);
h1("6. 고도화 ② 웨어러블 측정값 융합");
point("기기로 잰 혈압·체중을 기존 예측과 합쳤습니다. 체중은 좋아졌고 혈압은 좋아지지 않았습니다. 검진 이력 없는 사용자에게는 새 산출 경로가 생겼습니다.");
body(`검진일 전후 180일 안에 웨어러블 측정이 있는 검진을 짝지어(혈압 ${fu.sbp.n_pairs}쌍, 체중 ${fu.weight.n_pairs}쌍) 사용자 단위 5겹 교차검증을 10회 반복했습니다. 채택 규칙은 '기존 예측 대비 오차 차이의 95% 구간이 0 미만이면 채택, 개선 3% 이상이면서 더 넓은 창(±365일)에서 유의하면 조건부 채택'입니다.`);
figure(4, "측정값 융합의 효과", "U4_fusion.png", "왼쪽은 직전 검진이 있는 사용자(연청 기존 예측, 진청 융합), 오른쪽은 검진 이력이 없다고 가정한 경우(회색 성별·연령 평균, 파랑 측정값 반영). 막대 위 글씨가 채택 판정입니다.", 600, 343);
table(["항목", "대상", "기존 → 융합 오차", "차이의 95% 구간", "판정"], [
  ["수축기혈압", "직전 검진 보유", `${fu.sbp.with_prior_checkup.mae_base} → ${fu.sbp.with_prior_checkup.mae_fused}`, `[${fu.sbp.with_prior_checkup.fused_vs_base_ci95}]`, gateKo[fu.sbp.gate_with_prior]],
  ["이완기혈압", "직전 검진 보유", `${fu.dbp.with_prior_checkup.mae_base} → ${fu.dbp.with_prior_checkup.mae_fused}`, `[${fu.dbp.with_prior_checkup.fused_vs_base_ci95}]`, gateKo[fu.dbp.gate_with_prior]],
  hl(["체중 (BMI는 체중에서 파생)", "직전 검진 보유", `${fu.weight.with_prior_checkup.mae_base} → ${fu.weight.with_prior_checkup.mae_fused} kg (BMI ${m2.bmi_from_fused_weight.mae_carry_forward} → ${m2.bmi_from_fused_weight.mae_fused})`, `[${fu.weight.with_prior_checkup.fused_vs_base_ci95}], ±365일 [${m2.fusion_window_sensitivity.weight["365"].fused_vs_base_ci95}]`, gateKo[fu.weight.gate_with_prior]], C.amber),
  hl(["체중", "검진 이력 없음", `성별·연령 평균 ${fu.weight.no_prior_checkup.mae_korean_reference_only} → ${fu.weight.no_prior_checkup.mae_m0_measured} kg (R² ${fu.weight.no_prior_checkup.r2_m0})`, `[${fu.weight.no_prior_checkup.m0_vs_reference_ci95}]`, gateKo[fu.weight.gate_no_prior]], C.mint),
  hl(["수축기혈압", "검진 이력 없음", `${fu.sbp.no_prior_checkup.mae_korean_reference_only} → ${fu.sbp.no_prior_checkup.mae_m0_measured} (R² ${fu.sbp.no_prior_checkup.r2_m0})`, `[${fu.sbp.no_prior_checkup.m0_vs_reference_ci95}]`, "채택 (참고 표기)"], C.mint),
  ["이완기혈압", "검진 이력 없음", `${fu.dbp.no_prior_checkup.mae_korean_reference_only} → ${fu.dbp.no_prior_checkup.mae_m0_measured}`, `[${fu.dbp.no_prior_checkup.m0_vs_reference_ci95}]`, gateKo[fu.dbp.gate_no_prior]],
], [2000, 1500, 3000, 2038, 1100], { zebra: false });
body("웨어러블 혈압이 도움이 되지 않은 이유는 측정 횟수가 적고(쌍당 중앙 3회) 측정 자세·시간·기기가 표준화돼 있지 않아, 측정 횟수가 6회 이상인 사용자만 봐도 개선이 없었기 때문입니다. 체중은 기기 측정과 검진값의 상관이 0.96으로 높아 직전 검진값(가중치 0.18)보다 측정값(0.79)을 더 신뢰하는 조합이 선택됐습니다.");
h1("7. 고도화 ③ 시간 순서 검증과 채택하지 않은 실험");
point("'과거로 학습해 미래를 맞히는' 검증에서도 혈압 개선은 유의했습니다. 입력을 더 늘리는 시도는 효과가 없었습니다.");
table(["항목", "2025년 이전 학습 → 이후 검진 평가", "직전값 → 모델 오차", "차이의 95% 구간", "판정"], [
  ["수축기혈압", `학습 ${tp.sbp.n_train}건 / 평가 ${tp.sbp.n_test}건`, `${tp.sbp.mae_carry_forward} → ${tp.sbp.mae_model} (${tp.sbp.improve_pct}%)`, `[${tp.sbp.diff_ci95}]`, "통과"],
  ["이완기혈압", `학습 ${tp.dbp.n_train}건 / 평가 ${tp.dbp.n_test}건`, `${tp.dbp.mae_carry_forward} → ${tp.dbp.mae_model} (${tp.dbp.improve_pct}%)`, `[${tp.dbp.diff_ci95}]`, "통과"],
  hl(["공복혈당", `학습 ${tp.fasting_glucose.n_train}건 / 평가 ${tp.fasting_glucose.n_test}건`, `${tp.fasting_glucose.mae_carry_forward} → ${tp.fasting_glucose.mae_model} (${tp.fasting_glucose.improve_pct}%)`, `[${tp.fasting_glucose.diff_ci95}]`, "경계 (구간이 0에 걸침)"], C.amber),
  ["체중 · BMI", `평가 ${tp.weight.n_test}건`, `${tp.weight.mae_carry_forward} → ${tp.weight.mae_model} / ${tp.bmi.mae_carry_forward} → ${tp.bmi.mae_model}`, `[${tp.weight.diff_ci95}]`, "직전값 유지가 옳음을 재확인"],
], [1500, 2700, 2500, 1600, 1338], { zebra: false });
table(["채택하지 않은 실험", "결과", "판단"], [
  ["전체 방문 이력 통계(평균·횟수·변동) + 간·신장·혈색소 직전값을 입력에 추가", `교차검증 개선폭 수축기 ${ab.sbp.best_gain_pct}%, 이완기 ${ab.dbp.best_gain_pct}%, 혈당 ${ab.fasting_glucose.best_gain_pct}%`, "채택 기준 3% 미달"],
  ["예측값 기울기 재보정으로 고위험 과소예측 교정", `고위험 구간 편향 ${cal.sbp.actual_high.bias_pred_minus_actual} → ${cal.sbp.linear_recalibration.high_bias_after}`, "효과 없음 (4장)"],
  ["웨어러블 혈압 측정값 융합", "기존 예측 대비 개선 없음, 측정 6회 이상에서도 동일", "미채택 (6장)"],
  ["걸음·심박·수면으로 혈압 추정(이전 회차 실험)", "설명력 0에 가까움", "현 신호로는 불가"],
], [4400, 3300, 1938]);

// ================= PART III =================
partHead("PART III", "고도화 모델 재분석", "항목별 사용 가능 수준, 남은 문제와 보완 방법, 그리고 현재로서는 해결할 수 없는 제한입니다.");
h1("8. 고도화 모델 성능 요약");
point(`산출 대상이 ${up.m1_users}명에서 ${up.m2_users}명으로 늘었고, 기준 초과 안내는 네 문제 모두 '놓침 15% 이하'를 달성했습니다.`);
table(["항목", "산출 방식", "성능 (새 최종 검증 또는 융합 검증)", "사용 수준"], [
  hl(["혈압(수축·이완) 수치", "개인화 M1", `오차 ${sg.sbp.mae_model} / ${sg.dbp.mae_model} mmHg, 직전값보다 유의하게 정확, 시간 순서 검증 통과`, "의료진 검토용"], C.mint),
  hl(["공복혈당 수치", "개인화 M1", `오차 ${sg.fasting_glucose.mae_model} mg/dL, 유의. 시간 순서 검증은 경계`, "의료진 검토용"], C.mint),
  hl(["고혈압·혈당장애·비만·복부비만 안내", "플래그 + 새 기준점, 3단계 등급", `찾아낸 비율 ${pct(fv("hypertension_140_90")[RT].sensitivity)} / ${pct(fv("fasting_glucose_ge100")[RT].sensitivity)} / ${pct(fv("obesity_bmi_ge25")[RT].sensitivity)} / ${pct(fv("abdominal_obesity")[RT].sensitivity)}`, "의료진 검토용 (기준점은 의료진 승인 필요)"], C.mint),
  hl(["체중·BMI", "직전값 + 웨어러블 체중 융합", `오차 ${fu.weight.with_prior_checkup.mae_base} → ${fu.weight.with_prior_checkup.mae_fused} kg, 조건부 채택`, "참고 표기"], C.amber),
  hl(["검진 이력 없는 사용자의 체중 / 수축기혈압", "웨어러블 측정값 + 성별·연령 기준", `오차 ${fu.weight.no_prior_checkup.mae_m0_measured} kg / ${fu.sbp.no_prior_checkup.mae_m0_measured} mmHg`, "체중 사용 가능, 혈압은 참고"], C.amber),
  ["지질 4항목, 허리둘레", "교차 항목 모델 / 직전값 유지", "변화 없음 (설명력 낮음)", "참고용"],
  hl(["걸음·심박·수면을 반영한 예측, 이력 없는 사용자의 혈당·지질", "—", `정답지 ${fn.users_ge1d}명 < 30명`, "미검증"], C.rose),
], [2500, 2300, 3438, 1400], { zebra: false });
figure(5, "서비스 산출 범위 — 고도화 전과 후", "U5_coverage.png", `항목별로 값을 받는 사용자 수. 진청은 측정값 융합, 파랑은 검진 이력이 없거나 오래돼 기존에는 보류되던 사용자입니다. 전체 산출 대상은 ${up.m1_users}명에서 ${up.m2_users}명이 됐습니다.`, 600, 343);
h1("9. 문제점과 보완이 필요한 부분");
point("아래는 데이터가 쌓이거나 의사결정이 있으면 해결할 수 있는 항목입니다.");
table(["#", "문제점", "근거", "보완 방법"], [
  ["1", "고혈압 안내의 과다 분류", `안내 대상 ${pct(fv("hypertension_140_90")[RT].flagged_rate)}, 그중 실제 고혈압 ${pct(fv("hypertension_140_90")[RT].ppv)}`, "'주의' 등급은 재측정 권유, '높음'만 병원 안내로 이원화. 기준점은 의료진과 확정"],
  ["2", "공복혈당의 시간 순서 검증이 경계", `개선 구간 [${tp.fasting_glucose.diff_ci95}]`, "분기마다 재검증. 구간이 0 미만으로 내려오기 전에는 '검토용' 유지"],
  ["3", "체중 융합이 조건부 채택", `주 분석 구간 상한 ${fu.weight.with_prior_checkup.fused_vs_base_ci95[1]}`, "쌍이 100개를 넘으면 재평가 (현재 70쌍)"],
  ["4", "복부비만 판별력 하락", `${old.clf.abdominal_obesity.auroc} → ${sig.clf.abdominal_obesity.auroc}`, "재구축 때마다 추적. 0.9 미만이면 원인 분석"],
  ["5", "웨어러블 혈압 측정의 품질", "쌍당 측정 중앙 3회, 자세·시간 비표준", "앱에서 '아침 안정 시 2회' 측정 안내, 주 3회 이상 측정자를 별도 검증"],
  ["6", "운영 자동화 없음", "재구축·산출이 수동 실행", "주간 재구축, 데이터 현황·성능 추적 자동 기록"],
], [500, 2500, 3100, 3538]);
h1("10. 제한사항 — 현재로서는 해결할 수 없는 부분", true);
point("아래는 기법으로 풀 수 없고 시간·데이터·기기가 있어야 풀리는 항목입니다.");
table(["#", "제한", "이유", "풀리는 조건"], [
  hl(["1", "걸음·심박·수면이 검진값 예측에 기여하는지 알 수 없음", `'착용 뒤 검진' 정답지 ${fn.users_ge1d}명. 학습도 검증도 불가`, "정답지 30명 이상. 연 1회 검진 주기상 3~6개월 필요"], C.rose),
  hl(["2", "수치 예측 정확도의 상한", `검진값 자체의 개인 내 변동(수축기 ±${nc.sbp.sigma_within}). 남은 여지 최대 약 ${Math.round((1 - nc.sbp.mae_floor_estimate / sg.sbp.mae_model) * 100)}%`, "검진을 여러 번 재거나 가정 혈압을 표준화해 '참값'의 잡음을 줄여야 함"], C.rose),
  ["3", "혈당·지질을 웨어러블로 직접 볼 수 없음", "해당 측정 채널이 없음", "연속혈당측정기 등 새 기기 연동"],
  ["4", "검진 이력 없는 사용자의 이완기혈압·혈당·지질·BMI", "측정값 반영이 성별·연령 평균보다 낫지 않거나, 키 정보가 없음", "첫 검진 업로드 또는 프로필 키 수집"],
  ["5", "융합 검증이 '현재값 추정' 기준", "측정이 검진 뒤에 있는 쌍이 대부분. 엄밀한 '측정 → 이후 검진' 쌍은 7~8개", "시간이 지나 정방향 쌍이 쌓여야 함"],
  ["6", "검증 표본이 작음", `${HO} 61명, 고혈압 양성 ${fv("hypertension_140_90")[RT].positives}건 → 찾아낸 비율 구간 ${pct(fv("hypertension_140_90")[RT].sens_ci95[0])}~${pct(fv("hypertension_140_90")[RT].sens_ci95[1])}`, "사용자 증가. 같은 검증 집단을 반복해 본 데 따른 낙관 가능성도 새 사용자로만 해소"],
], [500, 2900, 3300, 2938], { zebra: false });
callout("다음 단계: ", "(1) 안내 기준점과 3단계 등급의 의료진 승인 · (2) 검진 결과 업로드 캠페인으로 정답지 30명 확보 · (3) 가정 혈압 측정 표준 안내 · (4) 주간 재구축 자동화. 네 가지 모두 모델 기법이 아니라 데이터와 운영의 과제입니다.");
ch.push(P([], { spacing: { after: 100 } }));
src(`근거 파일: 01_Results/data_status_2026-09-17.json · m2/m2_report.json · significance.json · configs/m2_rules.json · serving/m2_predictions_2026-09-17.parquet(가명키). 코드: src/sibc_checkup/m2.py, 자동 테스트 32개 통과. 본 모델은 진단·치료가 아닌 검진·진료 안내 보조 도구입니다.`);

const footer = new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TW }], children: [
  new TextRun({ text: "건강검진 예측 모델 고도화 결과 보고서 · 헬스커넥트(주) · 대외비", color: C.gray, size: 16 }), new TextRun({ text: "\t", color: C.gray, size: 16 }), new TextRun({ children: [PageNumber.CURRENT], color: C.gray, size: 16 })] })] });
const doc = new Document({
  styles: { default: { document: { run: { font: "Pretendard", color: C.text, size: 20 } } }, paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Pretendard", bold: true, color: C.navy, size: 28 }, paragraph: { outlineLevel: 0 } }] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "●", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } }, run: { color: C.gray, size: 12 } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134, header: 708, footer: 708 } } }, footers: { default: footer }, children: ch }],
});
Packer.toBuffer(doc).then(buf => { const out = "/Users/jaeho.oh/Downloads/SiBC_건강검진예측모델_고도화결과보고서_20260917.docx"; fs.writeFileSync(out, buf); console.log("written", out, buf.length); });
