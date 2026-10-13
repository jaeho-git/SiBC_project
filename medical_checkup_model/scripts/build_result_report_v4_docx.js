// 결과 보고서 v4(실측·예측 분리, 웨어러블 간접 신호 기여 명시). 원본 주석: 결과 보고서 v3(수치 예측 전용: 판정·안내는 판단 Agent 담당이므로 제외). 원본 주석: 결과 보고서(첫 보고용): 과거 데이터셋·이전 모델과의 비교 없이 '최신 데이터셋으로 만든 모델의 결과와 제한' 중심. 원본 주석: 고도화 결과 보고서 v2 — 경영진 보고용 간결판(2쪽 핵심 요약 + 본문 6장). 헬퍼는 v1과 동일 — 원본 주석: 모델 분석 보고서 v3 — v2(푸드렌즈 템플릿 포맷)에서 (1) 표 테두리를 표 단위로 통일(뷰어별 선 어긋남 방지), (2) '봉인' 등 전문 용어를 쉬운 말로 교체,
// (3) 보고서 구성표·장별 요점·그림 번호(1~6) 상호참조를 추가해 추적성을 높임. 실행: NODE_PATH=<docx 위치> node scripts/build_analysis_report_v3_docx.js
const fs = require("fs"), path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel, LevelFormat, ImageRun, Footer, PageNumber, TabStopType, VerticalAlign, TableLayoutType } = require("docx");
const ROOT = path.join(__dirname, ".."), ASSETS = path.join(__dirname, "v2_assets");
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





const sg = sig.m1, tp = m2.temporal, nc = m2.noise_ceiling, cal = m2.calibration;
const wc = J("01_Results/wearable_contribution.json"), ps = J("01_Results/predictions/prediction_summary_v2.json"), sch = J("configs/prediction_output_schema.json");
const wn = ds.wearable_now, bf = wn.by_feature, fn = ds.forward_now, ln = ds.labels_now;
const pct = x => Math.round(x * 100) + "%";
const gain = k => Math.round((1 - sg[k].mae_model / sg[k].mae_cf) * 100);
const room = Math.round((1 - nc.sbp.mae_floor_estimate / sg.sbp.mae_model) * 100);
const KOR = { sbp: "수축기혈압", dbp: "이완기혈압", fasting_glucose: "공복혈당", weight: "체중", bmi: "BMI", waist: "허리둘레", total_cholesterol: "총콜레스테롤", hdl: "HDL", ldl: "LDL", triglyceride: "중성지방" };
const ORDER = ["sbp", "dbp", "fasting_glucose", "weight", "bmi", "waist", "total_cholesterol", "hdl", "ldl", "triglyceride"];
const ph = wc.public_holdout, px = wc.own_proxy_vs_cuff, fw = wc.own_forward_reference, ag = ps.measured_vs_predicted_agreement_reference, cov = ps.coverage;
const maxGain = Math.max(...ORDER.map(k => ps.public_gain_grip[k])), maxGainItem = ORDER.find(k => ps.public_gain_grip[k] === maxGain);
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
ch.push(P([R("실측과 예측의 분리 · 웨어러블 신호의 실제 기여 · 검증 상태 · 제한사항", { size: 30 })], { spacing: { after: 5200 } }));
ch.push(P([R("오재호 과장", { bold: true, size: 26 })], { spacing: { after: 55 } }));
ch.push(P([R("AI플랫폼본부 SiBC · 데이터 기준일 2026-09-17 · 산출일 2026-09-18", { color: C.gray })], { spacing: { after: 36 } }));

// ================= 핵심 요약 =================
ch.push(P([R("EXECUTIVE SUMMARY", { bold: true, color: C.blue, size: 24 })], { spacing: { before: 90, after: 80 }, pageBreakBefore: true }));
ch.push(P([R("핵심 요약", { bold: true, size: 32 })], { spacing: { after: 140 } }));
callout("결론  ", `웨어러블로 직접 잴 수 있는 항목(혈압·체중·BMI)의 기기 측정값은 '실측'으로 분리하고, '예측'은 같은 항목의 측정값을 쓰지 않고 다른 데이터로만 추정한 값에 한정했습니다. 현재 검증된 예측은 과거 검진 이력에 기반한 것이며 웨어러블을 쓰지 않습니다. 걸음·활동량 같은 웨어러블 간접 신호는 공공데이터에서 체중·BMI·허리둘레 오차를 4~9% 줄였지만 혈압·혈당·지질에는 1% 이하만 기여했고, 우리 사용자로는 아직 검증할 수 없습니다.`);
ch.push(P([], { spacing: { after: 120 } }));
kpi([
  { label: "검증된 예측 (검진 이력 기반)", value: `−${gain("sbp")}% · −${gain("dbp")}%`, note: "혈압 오차, 직전 검진값 대비. 웨어러블 미사용", fill: C.mint, color: C.green },
  { label: "웨어러블 신호의 기여 (공공데이터)", value: `≤1% · ${maxGain.toFixed(0)}%`, note: `혈압·혈당·지질 ≤1%, 최대는 ${KOR[maxGainItem]} ${maxGain.toFixed(1)}%`, fill: C.amber, color: "D97706" },
  { label: "웨어러블 반영 예측의 자체 검증", value: "불가", note: `'착용 뒤 검진' ${fn.users_ge1d}명 < 기준 30명. 참고값으로만 산출`, fill: C.rose, color: C.red },
  { label: "산출 대상", value: `${ps.users}명`, note: `실측·예측 ${ps.rows.toLocaleString()}행. 검진 보유 ${ps.with_checkup}명` },
]);
sub("결과 요약");
table(["구분", "결과", "상태"], [
  ["실측 (예측 아님)", `혈압계 ${cov.sbp["실측"]}명, 체중계 ${cov.weight["실측"]}명, BMI(체중계+신장비) ${cov.bmi["실측"]}명. 측정 요약(중앙값·횟수·기간)만 산출`, "제공"],
  hl(["예측 ① 검진 이력 기반", `과거 검진값·경과일·추세로 추정. 혈압 오차 −${gain("sbp")}% / −${gain("dbp")}%, 공복혈당 −${gain("fasting_glucose")}% (직전값 대비, 검증 61명). 웨어러블 미사용`, "검증됨"], C.mint),
  hl(["예측 ② 검진 이력 + 웨어러블 간접 신호", `걸음·활동량·활동시간·악력을 더한 통합 모델. ${cov.sbp["이력+웨어러블 예측(참고)"]}명에게 산출. 자체 검증 불가, 공공데이터 기여 ≤1%(혈압·혈당·지질)~${maxGain.toFixed(0)}%(${KOR[maxGainItem]})`, "참고용"], C.amber),
  hl(["예측 ③ 웨어러블만 (검진 이력 없음)", `걸음·활동량 + 성별·연령. ${cov.sbp["웨어러블만 예측(미검증)"]}명에게 산출. 공공데이터 내부 설명력 R² 0.02~0.24`, "미검증"], C.rose),
  hl(["웨어러블→혈압 간접 추정의 한계", `자체 사용자 ${px.sbp.n_users}명(${px.sbp.n_rows}일)에서 심박·수면·걸음으로 혈압계 값을 맞히는 실험: 설명력 R² ${px.sbp.r2}(수축기)·${px.dbp.r2}(이완기). 현 신호로는 사실상 불가`, "부정적 결과"], C.rose),
], [2600, 5600, 1438], { zebra: false });
sub("결정이 필요한 사항");
bullet("예측 항목의 범위.", "혈압·체중·BMI는 실측이 있으므로 예측의 실익이 적습니다. 예측의 본래 목표를 공복혈당·지질·허리둘레처럼 웨어러블로 잴 수 없는 항목으로 좁힐지 결정이 필요합니다.");
bullet("검진 결과 업로드 캠페인.", "'착용 뒤 검진' 30명 확보가 웨어러블 반영 예측을 검증하는 유일한 경로입니다. 3~6개월이 걸립니다.");
bullet("새 신호 확보 검토.", "현재 채널(걸음·심박·수면)로는 혈당·지질을 간접 추정할 근거가 없습니다. 연속혈당측정기 등 새 기기 연동 여부를 검토해야 합니다.");

// ================= 본문 =================
h1("1. 무엇을 실측이라 하고 무엇을 예측이라 하는가", true);
table(["구분", "정의", "해당 항목", "산출 내용"], [
  ["실측 (MEASURED)", "웨어러블 기기가 같은 항목을 직접 잰 값", "혈압(혈압계), 체중(체중계), BMI(체중계 값 × 직전 검진 신장비)", "기준일 이전 180일 중앙값, 측정 횟수·기간. 예측 구간·정확도 없음"],
  ["예측 ① HISTORY", "과거 검진값·경과일·추세 + 성별·연령으로 추정. 웨어러블 미사용", "10개 항목", "예측값, 85% 구간. 자체 사용자 61명으로 검증"],
  ["예측 ② HISTORY_WEARABLE", "위 입력 + 웨어러블 간접 신호(7일 걸음·활동량 백분위·활동시간·악력)", "10개 항목", "예측값, 85% 구간(공공 잔차 기준). 참고용"],
  ["예측 ③ WEARABLE_ONLY", "검진 이력 없음. 간접 신호 + 성별·연령만", "10개 항목", "예측값, 85% 구간(공공 잔차 기준). 미검증"],
], [2100, 3200, 2300, 2038], { compact: true });
body("어떤 예측 경로도 같은 항목의 웨어러블 측정값(혈압계·체중계)을 입력으로 쓰지 않습니다. 이 규칙은 코드에서 자동 검사합니다. 상태 판정과 안내는 후단 판단 Agent가 담당하므로 산출하지 않습니다.");
body(`그림 1의 왼쪽은 데이터 종류별 사용자 수입니다. 파랑은 예측 입력이 되는 간접 신호(걸음 ${bf.step_count.users}명, 심박 ${bf.heartrate_median.users}명, 수면 ${bf.sleep_duration_min.users}명), 연한 파랑은 실측 채널(혈압계 ${bf.bp_systolic_measured.users}명, 체중계 ${bf.body_weight_measured.users}명)입니다. 오른쪽은 간접 신호로 검진값을 예측하도록 학습·검증하는 데 필요한 '웨어러블 착용 뒤에 받은 검진' 기록으로, 현재 ${fn.users_ge1d}명이어서 기준 30명에 미치지 못합니다. 이 때문에 웨어러블 간접 신호를 쓰는 예측은 공공데이터(미국 NHANES 활동량+검진 9,981건)로만 학습했고 우리 사용자로는 검증하지 못했습니다.`);
figure(1, "보유 데이터와 학습·검증 데이터 부족", "Q1_data.png", "", 470, 268);

h1("2. 웨어러블 간접 신호는 검진값 예측에 얼마나 기여하는가", true);
body(`그림 2는 공공데이터 홀드아웃 ${wc.n_public_test.toLocaleString()}건에서 성별·연령만 쓴 모델을 기준으로, 걸음·활동량·활동시간을 더했을 때(파랑)와 악력까지 더했을 때(진한 파랑) 오차가 얼마나 줄었는지 보여 줍니다. 체중·BMI·허리둘레는 4~9% 줄었지만 혈압·공복혈당·지질은 1% 이하이고 중성지방은 오히려 늘었습니다. 채택 기준으로 쓰는 3%를 넘는 항목은 체중·BMI·허리둘레뿐입니다. 이 수치는 미국 공공데이터의 결과이며 우리 사용자 성능이 아닙니다.`);
figure(2, "웨어러블 간접 신호의 예측 기여 (공공데이터 홀드아웃)", "Q2_contribution.png", "", 470, 268);
table(["항목", "성별·연령만 → +활동 신호 → +악력 (오차)", "기여율", "공공 설명력 R²"], [
  ...ORDER.map(k => { const r = ph[k]; return [KOR[k], `${r.demo_only.mae} → ${r.demo_activity.mae} → ${r.demo_activity_grip.mae}`, `${ps.public_gain_grip[k] >= 0 ? "+" : ""}${ps.public_gain_grip[k]}%`, `${r.demo_activity_grip.r2}`]; }),
], [2000, 3800, 1600, 2238], { compact: true });
body(`우리 사용자로 확인할 수 있는 근거는 두 가지뿐입니다. 첫째, 심박·수면·걸음으로 웨어러블 혈압계 값을 맞히는 대리 실험(${px.sbp.n_users}명, ${px.sbp.n_rows}일)에서 설명력이 수축기 ${px.sbp.r2}, 이완기 ${px.dbp.r2}로 0에 가까웠습니다. 둘째, '착용 뒤 검진' ${fw.n_users}명에 통합 모델을 적용한 결과는 항목당 ${fw.targets.sbp.n_forward}~${fw.targets.weight.n_forward}건이어서 성능 주장에 쓸 수 없습니다. 따라서 현재 채널로는 혈압·혈당·지질을 웨어러블 간접 신호로 예측한다고 말할 근거가 없습니다.`);

h1("3. 검증된 예측 — 검진 이력 기반", true);
body(`그림 3은 자체 검증 사용자 61명에서 항목별 평균 오차를 비교합니다. 연한 파랑은 직전 검진값을 그대로 쓴 경우, 진한 파랑은 검진 이력 기반 예측, 회색은 검진값의 자연 변동이 허용하는 오차 하한(추정)입니다. 혈압은 직전값보다 ${gain("sbp")}%·${gain("dbp")}%, 공복혈당은 ${gain("fasting_glucose")}% 정확하며 통계적으로 유의합니다. 이 예측은 웨어러블을 전혀 쓰지 않으므로 '웨어러블 기반 예측'이 아니라 '검진 이력 기반 예측'입니다.`);
figure(3, "검진 이력 기반 예측의 정확도", "Q3_history.png", "", 470, 268);
table(["항목", "오차: 직전값 → 예측", "개선", "시간 순서 검증", "경로"], [
  ["수축기혈압", `${sg.sbp.mae_cf} → ${sg.sbp.mae_model} mmHg`, `−${gain("sbp")}%, 유의`, `−${tp.sbp.improve_pct}%, 통과`, "개인화 모델"],
  ["이완기혈압", `${sg.dbp.mae_cf} → ${sg.dbp.mae_model} mmHg`, `−${gain("dbp")}%, 유의`, `−${tp.dbp.improve_pct}%, 통과`, "개인화 모델"],
  ["공복혈당", `${sg.fasting_glucose.mae_cf} → ${sg.fasting_glucose.mae_model} mg/dL`, `−${gain("fasting_glucose")}%, 유의`, `−${tp.fasting_glucose.improve_pct}%, 경계`, "개인화 모델"],
  ["체중 · BMI · 허리둘레", "모델 개선 3% 미달", "—", "—", "직전값 유지"],
  ["지질 4종", "반복 검진 63명, 설명력 낮음", "—", "—", "직전값 유지 / 다른 항목 기반"],
], [2100, 2700, 1500, 1700, 1638], { compact: true });
body(`예측값은 실제 고위험자의 값을 낮게 보는 경향이 있습니다(실제 수축기 140 이상인 사람을 평균 ${Math.abs(cal.sbp.actual_high.bias_pred_minus_actual)} mmHg 낮게). 보정으로 고쳐지지 않는 평균 회귀 현상이므로 예측값과 함께 85% 구간을 내보내며, 판단 Agent가 상한을 함께 보도록 명세에 적었습니다.`);
sub("실측과 예측의 일치도 (참고)");
body(`같은 사용자에게 실측과 예측이 모두 있는 경우 둘의 차이를 보면, 수축기혈압은 검진 이력 기반 예측이 혈압계 실측과 평균 ${ag.sbp_HISTORY.mae_vs_measured} mmHg(${ag.sbp_HISTORY.n}명), 웨어러블 신호를 더한 예측이 ${ag.sbp_HISTORY_WEARABLE.mae_vs_measured} mmHg(${ag.sbp_HISTORY_WEARABLE.n}명) 차이가 났습니다. 체중은 각각 ${ag.weight_HISTORY.mae_vs_measured} kg과 ${ag.weight_HISTORY_WEARABLE.mae_vs_measured} kg입니다. 혈압계 측정은 검진 측정과 조건이 달라 정답이 아니므로 참고치입니다.`);

h1("4. 산출 범위와 판단 Agent 연계 명세", true);
body(`그림 4는 항목별로 값을 받는 사용자 수를 실측, 검진 이력 기반 예측, 검진 이력+웨어러블 예측, 웨어러블만 예측으로 나눠 보여 줍니다. 전체 ${ps.users}명 가운데 검진 이력 보유자는 ${ps.with_checkup}명입니다. 혈압·체중은 실측이 ${cov.sbp["실측"]}·${cov.weight["실측"]}명에게 있고, 공복혈당·허리둘레·지질은 실측 채널이 없어 예측만 있습니다. 웨어러블 간접 신호가 있는 사용자(7일 걸음 기록)는 ${cov.sbp["이력+웨어러블 예측(참고)"] + cov.sbp["웨어러블만 예측(미검증)"]}명입니다.`);
figure(4, "항목별 산출 범위 — 실측과 예측을 분리", "Q4_coverage.png", "", 470, 268);
table(["필드", "의미"], [
  ["kind", "MEASURED(실측) / PREDICTED(예측)"],
  ["method", "DEVICE, DEVICE_DERIVED(실측) / HISTORY, HISTORY_WEARABLE, WEARABLE_ONLY(예측)"],
  ["validation", "VALIDATED_OWN(자체 검증) / REFERENCE_ONLY(자체 검증 불가, 참고) / UNVALIDATED(미검증) / N/A(실측·보류)"],
  ["value, lower, upper", "실측 중앙값 또는 예측값. 예측 행만 85% 구간(HISTORY는 자체 검증 잔차, 나머지는 공공 잔차 기준)"],
  ["uses_wearable, inputs", "웨어러블 사용 여부와 사용한 입력의 설명"],
  ["abstain_reason", "no_prior_checkup, stale_anchor, no_wearable_signal, no_checkup_and_no_wearable_signal, no_demographics"],
  ["basis_prev_checkup_*, measured_*", "예측 행의 직전 검진값·검진일 / 실측 행의 측정 횟수·기간"],
], [2600, 7038], { compact: true });
body(`명세 버전 ${sch.version}. 보장 사항: 어떤 예측 행도 같은 항목의 웨어러블 측정값을 입력으로 쓰지 않으며, 판정·플래그·안내·변화 방향을 포함하지 않습니다.`);

h1("5. 제한사항과 보완 계획", true);
table(["제한 (현재 해결 불가)", "이유", "풀리는 조건"], [
  hl(["웨어러블 간접 신호 기반 예측의 검증", `'착용 뒤 검진' ${fn.users_ge1d}명. 우리 사용자로 학습·검증 불가`, "30명 이상 확보 (3~6개월)"], C.rose),
  hl(["혈압·혈당·지질을 웨어러블로 예측", "공공데이터 기여 ≤1%, 자체 대리 실험 설명력 ≈0. 현 채널(걸음·심박·수면)에 정보가 거의 없음", "새 신호(연속혈당측정, PPG 파형 등) 확보"], C.rose),
  ["수치 예측 정확도의 상한", `검진값 자체가 같은 사람도 ±${nc.sbp.sigma_within} mmHg 변동. 남은 여지 약 ${room}%`, "반복 측정으로 기준값의 변동을 줄여야 함"],
  ["고위험 구간의 과소 예측", "평균 회귀 현상. 재보정으로 교정되지 않음", "판단 Agent가 예측 구간 상한을 함께 사용"],
  ["검증 표본이 작음", "검증 61명", "사용자 증가"],
], [3100, 3800, 2738], { zebra: false, compact: true });
table(["보완 과제", "현재 상태", "보완 방법"], [
  ["예측 항목 범위 재정의", "10개 항목 모두 예측 산출", "실측 채널이 있는 항목(혈압·체중·BMI)은 실측 우선, 예측은 잴 수 없는 항목 중심"],
  ["웨어러블 반영 예측의 검증", "참고용 산출만", "'착용 뒤 검진' 30명 도달 시 자동 평가 → 유의하면 검증됨으로 승격"],
  ["간접 신호 확장", "7일 걸음·활동량·악력만 통합 모델 입력", "심박·수면은 공공데이터에 대응 항목이 없어 자체 정답지 확보 후 학습"],
  ["판단 Agent 연계", "명세 v2.0", "Agent가 실측·예측·검증 상태를 어떻게 쓸지 확인 후 확정"],
  ["운영 자동화", "수동 갱신", "주간 자동 갱신과 검증 상태 추적"],
], [2700, 3200, 3738], { compact: true });
callout("다음 단계  ", "① 예측 항목 범위 결정  ② 검진 결과 업로드 캠페인('착용 뒤 검진' 30명)  ③ 새 신호 확보 검토  ④ 판단 Agent와 명세 확정.");
src("근거 파일: 01_Results/predictions/predictions_long_2026-09-18.parquet(가명키) · configs/prediction_output_schema.json · 01_Results/wearable_contribution.json · 01_Results/significance.json · 01_Results/proxy/proxy_report.json. 본 모델은 진단·치료가 아닌 검진·진료 안내 보조 도구의 수치 입력을 제공합니다.");

const footer = new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TW }], children: [
  new TextRun({ text: "건강검진 예측 모델 결과 보고서 · 헬스커넥트(주) · 대외비", color: C.gray, size: 16 }), new TextRun({ text: "\t", color: C.gray, size: 16 }), new TextRun({ children: [PageNumber.CURRENT], color: C.gray, size: 16 })] })] });
const doc = new Document({
  styles: { default: { document: { run: { font: "Pretendard", color: C.text, size: 20 } } }, paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Pretendard", bold: true, color: C.navy, size: 28 }, paragraph: { outlineLevel: 0 } }] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "●", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } }, run: { color: C.gray, size: 12 } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134, header: 708, footer: 708 } } }, footers: { default: footer }, children: ch }],
});
Packer.toBuffer(doc).then(buf => { const out = "/Users/jaeho.oh/Downloads/SiBC_건강검진예측모델_결과보고서_20260918.docx"; fs.writeFileSync(out, buf); console.log("written", out, buf.length); });
