// 모델 분석 보고서 v3 — v2(푸드렌즈 템플릿 포맷)에서 (1) 표 테두리를 표 단위로 통일(뷰어별 선 어긋남 방지), (2) '봉인' 등 전문 용어를 쉬운 말로 교체,
// (3) 보고서 구성표·장별 요점·그림 번호(1~6) 상호참조를 추가해 추적성을 높임. 실행: NODE_PATH=<docx 위치> node scripts/build_analysis_report_v3_docx.js
const fs = require("fs"), path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel, LevelFormat, ImageRun, Footer, PageNumber, TabStopType, VerticalAlign, TableLayoutType } = require("docx");
const ROOT = path.join(__dirname, ".."), ASSETS = path.join(__dirname, "report_assets");
const audit = JSON.parse(fs.readFileSync(path.join(ROOT, "01_Results/model_audit.json"), "utf8"));
const sig = JSON.parse(fs.readFileSync(path.join(ROOT, "01_Results/significance.json"), "utf8"));
const C = { navy: "0A3D9A", blue: "0A64FC", gray: "6B7280", text: "111827", red: "D92D20", line: "D1D5DB", zebra: "F8FAFC", amber: "FEF3C7", pale: "F1F5FF", green: "15803D", rose: "FDECEA", mint: "E8F5E9" };
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, LINE = { style: BorderStyle.SINGLE, size: 4, color: C.line };
const TW = 9638; // 본문 폭(twip)
const ch = [];
const R = (t, o = {}) => new TextRun({ text: t, bold: !!o.bold, color: o.color, size: o.size });
const P = (runs, o = {}) => new Paragraph({ spacing: Object.assign({ after: 110, line: 295, lineRule: "auto" }, o.spacing || {}), keepNext: o.keepNext, pageBreakBefore: o.pageBreakBefore, alignment: o.align, children: runs });
const body = (t, o) => ch.push(P(typeof t === "string" ? [R(t)] : t, o));
const partHead = (label, title, sub) => { ch.push(P([R(label, { bold: true, color: C.blue, size: 24 })], { spacing: { before: 100, after: 80 }, pageBreakBefore: true })); ch.push(P([R(title, { bold: true, size: 32 })], { spacing: { after: 120 } })); ch.push(P([R(sub, { color: C.gray, size: 22 })], { spacing: { after: 200 } })); };
const h1 = t => ch.push(new Paragraph({ heading: HeadingLevel.HEADING_1, keepNext: true, spacing: { before: 320, after: 120 }, children: [R(t, { bold: true, color: C.navy, size: 28 })] }));
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
const m1 = sig.m1, clf = sig.clf, sub = audit.subgroup, srv = audit.serving;
const HO = "최종 검증"; // '봉인 테스트' 대체어: 학습에 쓰지 않고 따로 떼어 둔 사용자 59명으로 마지막에 1회 평가

// ================= 표지 =================
ch.push(P([R("헬스커넥트(주) · AI플랫폼본부 SiBC", { bold: true, size: 22 })], { spacing: { after: 55 } }));
ch.push(P([R("대외비 · CONFIDENTIAL", { bold: true, color: C.red, size: 18 })], { spacing: { after: 1450 } }));
ch.push(P([R("HEALTH CHECKUP PREDICTION MODEL — READINESS ASSESSMENT", { bold: true, color: C.blue, size: 24 })], { spacing: { after: 210 } }));
ch.push(P([R("건강검진 예측 모델 분석 보고서", { bold: true, size: 52 })], { spacing: { after: 110 } }));
ch.push(P([R("지금 실제로 쓸 수 있는 수준인가 — 구축 방법, 성능, 부족한 부분과 보완 순서", { size: 30 })], { spacing: { after: 300 } }));
ch.push(P([R("웨어러블 데이터로 건강검진 항목을 예측하는 모델의 실사용 준비도를 항목별로 판정하고, 구축 방법에서 잘 된 것과 빠진 것,", { size: 22 })], { spacing: { after: 40 } }));
ch.push(P([R("성능이 객관적으로 어느 수준인지, 무엇을 어떤 순서로 보완해야 하는지를 처음 보는 분도 따라갈 수 있도록 정리했습니다.", { size: 22 })], { spacing: { after: 4200 } }));
ch.push(P([R("오재호 과장", { bold: true, size: 26 })], { spacing: { after: 55 } }));
ch.push(P([R("AI플랫폼본부 SiBC", { color: C.gray })], { spacing: { after: 36 } }));

// ================= EXECUTIVE SUMMARY =================
ch.push(P([R("EXECUTIVE SUMMARY", { bold: true, color: C.blue, size: 24 })], { spacing: { before: 90, after: 80 }, pageBreakBefore: true }));
ch.push(P([R("결론", { bold: true, size: 32 })], { spacing: { after: 120 } }));
bullet("어디까지 쓸 수 있는가.", `검진 이력이 있는 사용자의 다음 혈압·공복혈당 예측과 비만·복부비만 플래그는 ${HO}(학습에 쓰지 않은 사용자 59명)에서 '직전 검진값 그대로'보다 통계적으로 유의하게 정확했습니다(수축기 ${m1.sbp.mae_cf}→${m1.sbp.mae_model} mmHg, 공복혈당 ${m1.fasting_glucose.mae_cf}→${m1.fasting_glucose.mae_model} mg/dL). 의료진 검토용 시범 적용이 가능한 수준입니다. → 3장·4장, 그림 2`);
bullet("무엇이 아직인가.", "프로젝트의 핵심 목적인 '웨어러블을 반영한 예측'과 '검진 이력 없는 사용자의 유사 검진값'은 검증되지 않았습니다. 현재 서비스에 쓰는 모델의 입력에 웨어러블 항목이 0개이고, 검증에 필요한 '웨어러블 착용 뒤 받은 검진' 정답지가 15건(12명)뿐이기 때문입니다. → 7장, 그림 1");
bullet("가장 위험한 결함은 무엇인가.", `모델이 고위험 영역에서 낮게 예측합니다. 실제 수축기 ≥140인 사람을 평균 ${Math.abs(sub.sbp.high_range.bias)} mmHg, 공복혈당 ≥126인 사람을 ${Math.abs(sub.fasting_glucose.high_range.bias)} mg/dL 낮게 봅니다. '병원에 가야 할 사람을 정상처럼 보이게' 하는 방향이라, 예측값만으로 병원 안내를 판단해서는 안 됩니다. → 6장, 그림 4`);
bullet("구축 방법은 적정한가.", "미래 정보 차단, 사용자 단위 검증 데이터 분리, 사전에 정한 채택 규칙, 강한 기준선, 신뢰구간, 데이터 이력 기록은 갖춰져 있습니다. 빠진 것은 웨어러블 항목 반영, 고위험 과소예측 보정, 한국인 보정의 서비스 적용, 시간 순서 검증, 성능 저하 감시입니다. → 9장");
callout("시사점: ", "현재 모델은 '검진 이력이 있는 사용자'를 위한 개인화 추정·위험 플래그 도구로는 의료진 검토 단계에 들어갈 수 있지만, 사용자에게 직접 노출하거나 웨어러블 기반 예측을 주장할 단계는 아닙니다. 성능을 올리는 지렛대는 모델 기법이 아니라 '착용 뒤 검진' 정답지의 확보이며, 실사용 전에는 고위험 과소예측 보정이 선행되어야 합니다.");
src(`자체 데이터 ${HO}(사용자 59명, 1회 평가) + 2026-09-17 감사(산출 범위·입력 의존도·하위집단 편향·분할 반복 안정성). 신뢰구간은 사용자 단위 부트스트랩(2,000회). 사용자 식별 정보는 사용하지 않았습니다.`);

ch.push(P([R("보고서 구성 — 어디서 무엇을 확인하는가", { bold: true, size: 24 })], { spacing: { before: 200, after: 100 }, keepNext: true }));
table(["PART", "장", "답하는 질문", "근거 그림"], [
  ["I. 지금 어디까지 왔는가", "1. 모델이 하는 일", "무엇을 입력받아 무엇을 내놓는가, 용어 설명", "—"],
  ["", "2. 구축 방법 한눈에", "어떤 데이터로 어떤 순서로 만들었는가", "그림 1 데이터·병목"],
  ["", "3. 항목별 준비도 판정", "항목별로 지금 어디까지 써도 되는가", "—"],
  ["II. 성능은 어느 수준인가", "4. 개인화 예측 정확도", "직전값보다 얼마나 정확하고 우연이 아닌가", "그림 2 오차 비교"],
  ["", "5. 기준 초과 판별", "'기준을 넘는가'를 얼마나 맞히는가", "그림 3 판별력"],
  ["", "6. 감사에서 드러난 결함", "어디서 틀리며 왜 위험한가", "그림 4 과소예측"],
  ["", "7. 웨어러블 반영 여부", "핵심 목적과 무엇이 어긋나는가", "—"],
  ["", "8. 서비스 산출 범위", "394명 중 누구에게 무엇을 줄 수 있는가", "그림 5 산출 경로"],
  ["III. 무엇을 보완해야 하는가", "9. 구축 방법 평가", "갖춰진 것과 빠진 것(결함 1~8)", "—"],
  ["", "10. 보완 우선순위·관문", "무엇을 어떤 순서로, 실사용 조건은", "—"],
  ["", "11. 의사결정 요청", "지금 결정이 필요한 4가지", "—"],
], [2350, 2250, 3238, 1800], { zebra: false, compact: true });

// ================= PART I =================
partHead("PART I", "지금 어디까지 왔는가", "무엇을 맞히는 모델이고, 어떤 데이터로 어떻게 만들었으며, 항목별로 어디까지 쓸 수 있는지 판정합니다.");
h1("1. 모델이 하는 일 — 과거 웨어러블과 검진으로 '오늘 검진하면 나올 값'을 추정");
point("검진 이력이 있으면 개인화 경로(M1), 없으면 웨어러블 전용 경로(M0). 지금 검증이 끝난 것은 M1뿐입니다.");
body("이 모델은 사용자의 예측 시점 이전 데이터(직전 검진값, 그 이후 누적된 웨어러블 요약, 성별·연령)로 검진 항목 10종(혈압 2, 신체계측 3, 공복혈당, 지질 4)의 현재 값을 추정합니다. 출력은 예측값과 85% 구간, 기준 초과 확률(플래그), 변화 방향이며, 근거가 부족하면 '보류'와 사유를 냅니다. 학습이 끝난 모델을 실제 사용자 394명에게 적용하는 단계를 '서비스 산출'이라 부릅니다. 아래 용어는 보고서 전체에서 같은 뜻으로 씁니다.");
table(["용어", "쉬운 설명"], [
  ["M1 (개인화 경로)", "직전 검진값을 개인 기준선으로 두고 다음 검진값을 추정. 현재 검증이 끝난 서비스 경로"],
  ["M0 (웨어러블 전용 경로)", "검진 이력 없이 웨어러블·인구통계만으로 추정. 공공데이터로 학습만 됐고 우리 사용자로는 검증 전"],
  [`${HO} (따로 떼어 둔 59명)`, "학습에 전혀 쓰지 않고 미리 분리한 사용자 20%(59명). 마지막에 한 번만 평가하며, 이 보고서의 모든 성능 수치는 여기서 나옴"],
  ["직전값 그대로 (기준선)", "'다음 검진도 지난번과 같다'고 보는 가장 강한 비교 기준. 이를 못 이기면 모델을 쓸 가치가 없음"],
  ["채택 규칙", "모델을 쓸지 직전값을 유지할지 미리 정해 둔 규칙(직전값보다 3% 이상 개선 등). 결과를 보고 고르지 않도록 사전에 고정"],
  ["MAE / AUROC", "평균 오차(낮을수록 정확) / 기준 초과 판별력(0.5 동전 던지기, 0.8 이상 양호, 0.9 이상 우수)"],
  ["95% 신뢰구간", "같은 실험을 반복했을 때 결과가 들어올 범위. 개선폭의 구간이 0을 포함하지 않으면 '우연이 아니다'로 판정"],
  ["정답지 ('착용 뒤 검진')", "웨어러블을 착용한 '뒤에' 받은 검진 기록. 웨어러블→검진 관계를 배우고 검증하려면 이 예시가 있어야 함"],
], [2500, 7138]);
h1("2. 구축 방법 한눈에");
point("공공데이터 1만 건으로 학습 폭을 넓히고, 평가는 우리 사용자 데이터로만 했습니다. 병목은 '착용 뒤 검진' 정답지 12명입니다.");
table(["단계", "무엇을 했나", "결과"], [
  ["1. 데이터 통합", "공공(NHANES 미국 9,981 · KNHANES 한국 592) + 자체 검진 1,549건(394명)을 한 테이블로, 출처 표시·가중치", "12,122행. 공공은 학습에만, 평가에는 0행"],
  ["2. 알고리즘 비교", "5개 후보(선형·랜덤포레스트·부스팅·신경망·혼합효과)를 사용자 단위 5회 교차검증으로 항목별 비교", "부스팅 5/10 1위 → 주 알고리즘, 항목별 최적 혼용"],
  ["3. 학습·튜닝", "통합 모델 v1.3, 개인화 M1 v3(개인차 반영 혼합효과·보정 구간·교차 항목), 기준 초과 판별 모델", "10항목 모델 + 플래그 4종 + 방향 2종"],
  [`4. ${HO}`, "사전 채택 규칙(직전값 대비 ≥3% 개선·5회 중 과반 승·학습 100명/검증 30명 이상)", "혈압·혈당은 모델 채택, 체중·BMI는 직전값 유지, 지질은 교차 항목 모델"],
  ["5. 서비스 산출", "사용자당 1행: 실제값·측정 요약·예측·구간·플래그·방향·보류 사유", "394명 산출, 구간 규칙 위반 0건, 가명키만 사용"],
], [2000, 4600, 3038]);
figure(1, "학습 데이터 구성과 웨어러블 검증의 병목", "E_data.png", "왼쪽은 통합 학습 테이블의 출처별 행 수(공공은 학습에만 사용). 오른쪽은 웨어러블→검진 검증에 쓸 수 있는 정답지 12명(빨강) 대 검증 시작 기준 30명(회색), 그리고 현재 개인화 모델이 학습한 검진 쌍 292명.", 540, 309);
h1("3. 항목별 실사용 준비도 판정");
point("혈압·혈당 예측과 비만 플래그는 의료진 검토용으로 가능, 웨어러블 전용·웨어러블 반영 예측은 검증 전입니다.");
table(["판정", "항목", "근거"], [
  hl(["제한적 사용 가능 (의료진 검토용)", "혈압·공복혈당 개인화 예측, 비만·복부비만 플래그", `${HO}에서 직전값보다 유의하게 정확, 분할 3회 반복에도 결과 동일. 단 수치 예측값 단독 병원 안내는 금지(6장)`], C.mint),
  hl(["참고용 (사용자 노출 비권장)", "고혈압·공복혈당장애 플래그, 지질 4항목, 변화 방향", "판별력 양호(AUROC 0.82)이나 개선 신뢰구간이 0 포함. 지질 설명력 R² 0.07~0.21"], C.amber),
  hl(["직전값 유지 (모델 가치 없음)", "체중·BMI·허리둘레", "직전값 자체 R² 0.95/0.91. 체중계 측정값이 더 유용"], C.zebra),
  hl(["사용 불가 (미검증)", "검진 이력 없는 사용자의 M0 예측", "검증 가능한 정답지 15건/12명 < 시작 기준 30명"], C.rose),
  hl(["목적 미충족 (핵심 갭)", "이력 보유자의 '웨어러블 반영' 예측", "서비스용 M1 입력에 웨어러블 항목 0개(정답지 부족으로 자동 제외)"], C.rose),
], [2300, 2900, 4438], { zebra: false });
callout("한 줄 판정: ", "검진 이력 보유자의 혈압·혈당 예측과 기준 초과 플래그는 의료진 검토용 시범 적용이 가능합니다. 웨어러블 반영·이력 없는 사용자 예측은 검증 전입니다.");

// ================= PART II =================
partHead("PART II", `성능은 객관적으로 어느 수준인가`, `${HO}(따로 떼어 둔 사용자 59명) 결과를 기준선·신뢰구간과 함께 보고, 감사에서 새로 드러난 결함을 짚습니다.`);
h1("4. 개인화 예측(M1) — 직전값보다 얼마나 정확한가");
point("혈압·공복혈당은 직전값보다 오차가 14~20% 줄었고 신뢰구간이 0을 포함하지 않아 우연이 아닙니다. 체중·BMI는 직전값이 이미 충분히 정확합니다.");
body(`혈압·공복혈당은 '직전 검진값 그대로'보다 오차가 줄었고, 사용자 단위 부트스트랩 95% 신뢰구간이 전부 개선 쪽에 있어 통계적으로 유의합니다. 검증 데이터 분할을 3번 다르게 해도 채택 결과가 같아 우연이 아닙니다. 체중·BMI는 직전값이 이미 설명력 R² 0.95/0.91로 정확해 모델을 쓰지 않는 것이 옳다는 결론이 안정적으로 재현됐습니다.`);
figure(2, `개인화 예측 정확도 (${HO}, 사용자 59명)`, "B_m1_mae.png", "연청 직전값 그대로, 진청 우리 모델(M1)의 평균 오차. 초록 글씨는 감소폭과 95% 신뢰구간(전체가 음수면 유의). 아래 표의 3~4열.", 540, 309);
table(["항목", "채택 경로", `평균 오차: 모델 vs 직전값`, "개선폭 (95% 신뢰구간)", "설명력 R²", "분할 3회 반복"], [
  ["수축기혈압", "모델(선형)", `${m1.sbp.mae_model} vs ${m1.sbp.mae_cf}`, `${m1.sbp.diff} [${m1.sbp.diff_ci95}]`, "0.31", "모델 채택 3/3"],
  ["이완기혈압", "모델(혼합효과)", `${m1.dbp.mae_model} vs ${m1.dbp.mae_cf}`, `${m1.dbp.diff} [${m1.dbp.diff_ci95}]`, "0.24", "모델 채택 3/3"],
  ["공복혈당", "모델(혼합효과)", `${m1.fasting_glucose.mae_model} vs ${m1.fasting_glucose.mae_cf}`, `${m1.fasting_glucose.diff} [${m1.fasting_glucose.diff_ci95}]`, "0.17", "모델 채택 3/3"],
  ["체중 · BMI · 허리둘레", "직전값 유지", "직전값 R² 0.95 / 0.91, 허리 오차 3.9 cm", "개선 3% 미달", "—", "직전값 유지 3/3"],
  ["지질 4항목", "교차 항목 모델", "이력 없어도 약 310명 예측", "모집단 평균 대비 ≥3%", "0.07~0.21", "—"],
], [1500, 1350, 2000, 1900, 1150, 1738]);
h1("5. 기준 초과 판별 — '다음 검진에서 기준을 넘는가'");
point("네 문제 모두 판별력 0.8 이상이지만, 기준선 대비 개선이 확정된 것은 비만·복부비만 둘뿐입니다.");
body("정확한 수치보다 서비스가 실제로 묻는 '기준을 넘는가'는 훨씬 잘 맞힙니다. 네 문제 모두 '직전 상태 유지' 기준선보다 높았지만, 신뢰구간으로 보면 비만·복부비만만 개선이 확정이고 고혈압·혈당장애는 표본이 더 필요합니다. 고중성지방 ≥150 플래그는 양성이 8건뿐이라 정책상 보류했습니다.");
figure(3, `기준 초과 판별력 (${HO})`, "C_auroc.png", "연청은 직전 상태 유지 기준선, 진청은 우리 모델, 오차막대는 95% 신뢰구간. 막대 아래 라벨은 기준선 대비 개선이 통계적으로 확정됐는지(유의/미확정)를 뜻합니다. 점선 0.5는 동전 던지기 수준입니다.", 600, 343);
table(["문제", "판별력 AUROC (95% CI)", "직전 상태 기준선", "개선폭 (95% CI)", "판정"], [
  ["고혈압 ≥140/90", `${clf.hypertension_140_90.auroc} [${clf.hypertension_140_90.auroc_ci95}]`, `${clf.hypertension_140_90.prior_auroc}`, `${clf.hypertension_140_90.diff_vs_prior} [${clf.hypertension_140_90.diff_ci95}]`, "판별력 양호, 개선 미확정"],
  ["공복혈당장애 ≥100", `${clf.fasting_glucose_ge100.auroc} [${clf.fasting_glucose_ge100.auroc_ci95}]`, `${clf.fasting_glucose_ge100.prior_auroc}`, `${clf.fasting_glucose_ge100.diff_vs_prior} [${clf.fasting_glucose_ge100.diff_ci95}]`, "경계 (구간이 0에 걸침)"],
  hl(["비만 BMI≥25", `${clf.obesity_bmi_ge25.auroc} [${clf.obesity_bmi_ge25.auroc_ci95}]`, `${clf.obesity_bmi_ge25.prior_auroc}`, `${clf.obesity_bmi_ge25.diff_vs_prior} [${clf.obesity_bmi_ge25.diff_ci95}]`, "개선 유의"], C.mint),
  hl(["복부비만", `${clf.abdominal_obesity.auroc} [${clf.abdominal_obesity.auroc_ci95}]`, `${clf.abdominal_obesity.prior_auroc}`, `${clf.abdominal_obesity.diff_vs_prior} [${clf.abdominal_obesity.diff_ci95}]`, "개선 유의"], C.mint),
], [1900, 2200, 1500, 2200, 1838], { zebra: false });
h1("6. 감사에서 드러난 결함 — 고위험 영역 과소예측");
point("평균으로 보면 편향이 거의 없지만, 실제 기준을 넘는 사람만 보면 크게 낮게 예측합니다. 서비스 목적상 가장 위험한 오류입니다.");
body(`성별·연령·직전 검진 경과일로 나누면 편향이 ±5 이내이고 모든 구간에서 직전값보다 정확합니다. 그러나 실제값이 임상 기준을 넘는 고위험 영역에서는 크게 낮게 예측합니다. 혼합효과·선형 모델이 개인 값을 모집단 평균 쪽으로 끌어당기는 특성 때문이며, '병원에 가야 할 사람을 정상처럼 보이게' 하는 방향이라 서비스 목적에 가장 위험한 오류입니다.`);
table(["항목", "고위험 구간", "인원", "편향 (예측 − 실제)", "모델 평균 오차"], [
  hl(["수축기혈압", "실제 ≥140 (고혈압 영역)", `${sub.sbp.high_range.n}`, `${sub.sbp.high_range.bias}`, `${sub.sbp.high_range.mae}`], C.rose),
  hl(["이완기혈압", "실제 ≥90 (고혈압 영역)", `${sub.dbp.high_range.n}`, `${sub.dbp.high_range.bias}`, `${sub.dbp.high_range.mae}`], C.rose),
  hl(["공복혈당", "실제 ≥126 (당뇨 영역)", `${sub.fasting_glucose.high_range.n}`, `${sub.fasting_glucose.high_range.bias}`, `${sub.fasting_glucose.high_range.mae}`], C.rose),
], [1500, 3000, 1300, 2000, 1838], { zebra: false });
figure(4, "고위험 영역 과소예측", "D_bias.png", "편향 = 예측 − 실제. 연청(전체 사용자 평균)은 ±3 이내지만 빨강(실제값이 임상 기준을 넘는 고위험 영역)은 크게 음수, 즉 위험한 사람을 낮게 예측합니다. 괄호는 해당 영역 인원. 빨강 막대가 위 표의 편향 값입니다.");
callout("핵심: ", "수치 예측값을 단독으로 병원 안내 근거로 쓰면 안 됩니다. 기준 초과 플래그(판별 모델)는 고위험 영역을 별도로 학습하므로 반드시 병행하고, 실사용 전에 고위험 구간 보정(10장 순위 1)을 완료해야 합니다.", C.amber, "D97706", false);
h1("7. 서비스용 모델은 웨어러블을 보지 않는다 — 핵심 목적과의 갭");
point("세 모델 모두 '직전값·직전-직전값·연령'에만 의존합니다. 원인은 기법이 아니라 '착용 뒤 검진' 정답지가 15건뿐이라는 데이터 문제입니다.");
body(`입력 의존도 분석(${HO} 데이터에서 항목 하나를 무작위로 섞었을 때 오차가 얼마나 커지는지)으로 확인한 결과, 세 모델(수축기·이완기·공복혈당) 모두 상위 3개 입력이 '직전값 · 직전-직전값 · 연령'이고 웨어러블 입력은 0개입니다. 웨어러블 수집이 2025-12에 시작돼 '착용 뒤 검진' 학습 예시가 15건(전체의 1.4%)뿐이라, 결측 95% 초과 입력 자동 제외 규칙에 걸렸기 때문입니다. 서비스 산출 자체는 '마지막 검진 + 그 이후 웨어러블'을 조립하므로 설계는 목적과 맞고, 어긋난 곳은 학습 데이터입니다. 웨어러블 항목 4개를 쓰는 통합 모델 v1.3을 정답지 15건에 적용하면 이완기 4.67 vs 직전값 6.71, 공복혈당 8.41 vs 13.0으로 유리한 방향이 보이지만, 표본이 작아 성능 주장에는 쓸 수 없습니다.`);
h1("8. 서비스 산출 범위 — 394명 중 누구에게 무엇을 주는가");
point("혈압·혈당은 82%에게 예측을 제공하고 18%는 보류. 사용자의 1/3은 웨어러블 미착용이라 웨어러블 경로가 검증돼도 대상이 아닙니다.");
body(`394명 산출에서 혈압·공복혈당은 320~323명(82%)에 예측을 제공하고 71~74명은 보류합니다(검진 이력 없음 ${srv.abstain_reasons_sbp.no_prior_checkup}, 직전 검진 3년 초과 ${srv.abstain_reasons_sbp.stale_anchor}). 지질은 교차 항목 모델로 보류가 1명까지 줄었습니다. 웨어러블 충분성은 A등급(30일 중 21일 이상) 183명(46%), 미착용 136명(35%)입니다.`);
figure(5, "서비스 산출 범위 (394명)", "F_coverage.png", "항목별 산출 경로: 진청은 모델 예측, 파랑은 교차 항목 모델(참고), 연청은 직전값 유지, 회색은 보류. 막대 안 숫자는 사용자 수.");

// ================= PART III =================
partHead("PART III", "무엇을 보완해야 하는가", "구축 방법에서 갖춰진 것과 빠진 것(결함 1~8), 보완 우선순위, 그리고 실사용 관문입니다.");
h1("9. 구축 방법 평가 — 갖춰진 것과 빠진 것 (결함 1~8)");
point("검증 설계의 기본은 갖춰져 있습니다. 실사용을 막는 것은 치명 결함 2건(웨어러블 입력 없음, 고위험 과소예측)이며 10장의 우선순위는 이 번호를 참조합니다.");
body(`갖춰진 것: 미래 정보 차단(검진일 이전 데이터만 사용, 자동 테스트로 강제), 사용자 단위 ${HO} 데이터 20% 분리와 5겹 교차검증, ${HO} 데이터를 보지 않고 정한 채택 규칙(소표본 착시였던 지질 R² −1.4를 실제로 차단), 가장 강한 기준선(직전값 유지·직전 상태 유지) 포함, 사용자 단위 부트스트랩 신뢰구간, 입력 정의·모델 등록부·규칙 파일의 이력 기록, 명목 85% 구간의 실제 적중률 0.80~0.93. 아래는 빠진 것입니다.`);

table(["결함", "부족한 부분", "왜 문제인가", "심각도"], [
  hl(["1", "웨어러블 입력이 서비스용 모델에 없음", "정답지 15건 → 자동 제외. 프로젝트 목적과 직접 충돌", "치명"], C.rose),
  hl(["2", "고위험 영역 과소예측 미보정", "수축기≥140 −13, 혈당≥126 −36. 병원 안내에 가장 위험한 오류 방향", "치명"], C.rose),
  hl(["3", "한국인 보정 서비스 미적용", "KNHANES 기준표는 있으나 서비스 산출에 미연결. 미국 데이터 82% 통합 모델 사용 시 필수", "높음"], C.amber),
  hl(["4", "시간 순서 검증 부재", `${HO}는 사용자 분할. '과거로 학습해 미래 예측' 재현성은 정답지 15건으로만 확인`, "높음"], C.amber),
  ["5", "성능 저하 감시·재학습 자동화 없음", "기기·사용자 구성 변화 시 성능 저하를 감지할 장치 없음", "중간"],
  ["6", `${HO} 데이터 59명 — 신뢰구간 넓음`, "하위집단(연령대 21~67명) 결론 불안정", "중간"],
  ["7", "임상 임계값·변화 기준폭 의료진 검토 미실시", "문헌 기준. 서비스 맥락(가정방문)의 승인 필요", "중간"],
  ["8", "자기지도 표현학습·대리 학습 미활용", "현 신호·표본에서 기여 없음(표현학습 과적합, 심박→혈압 R²≈0)", "낮음"],
], [700, 2800, 4800, 1338], { zebra: false });
h1("10. 보완 우선순위와 실사용 관문");
point("순위 1·2·4를 끝내면 의료진 검토용 시범 적용, 정답지 30명 확보 뒤 사용자 노출, 의료진 승인 뒤 병원 연계 순입니다.");
table(["순위", "과제 (관련 결함)", "방법", "효과", "기간"], [
  hl(["1", "고위험 과소예측 보정 (결함 2)", "플래그 양성 시 구간 상한 표시, 고위험 가중 보조 모델, 극단값 오차 보정표", "병원 안내 누락 위험 제거 — 실사용 전제", "1~2주"], C.rose),
  hl(["2", "웨어러블 반영 서비스 산출 — 결합 방식 (결함 1)", "검증된 M1 기본 + 통합 모델의 웨어러블 변화분, '참고 추정치' 라벨. 이력 없는 사용자는 M0 유사 검진값", "핵심 목적 충족(검증 전 참고용)", "2주"], C.rose),
  hl(["3", "'착용 뒤 검진' 정답지 캠페인 (결함 1·6)", "연례 검진자 180명 업로드 유도, 자동 평가로 30명 도달 추적", "웨어러블 기여 검증의 유일한 경로", "3~6개월"], C.rose),
  hl(["4", "한국인 보정 서비스 적용 (결함 3)", "KNHANES 성별×연령대 기준표에 통합 모델 출력을 분위 정합", "미국 데이터 편향 제거", "1주"], C.amber),
  hl(["5", "시간 순서 검증 (결함 4)", "2025년 이전 학습 → 2025~2026 검진 평가", "미래 예측 재현성 확인", "1주"], C.amber),
  hl(["6", "의료진 검토 파일럿 (결함 7)", "예측·구간·플래그·방향 검토 화면, 임계값·변화 기준폭 승인, 피드백 정답", "임상 타당성·규칙 확정", "1~2개월"], C.amber),
  ["7", "감시·재학습 자동화 (결함 5)", "성능 저하·구간 적중률·양성률 대시보드, 분기 재학습, 이력 자동 기록", "운영 안정성", "2~3주"],
  ["8", "후순위: 지질 정답 축적, 새 신호 검토 (결함 8)", "반복 지질 검진 업로드 후 재시도 · PPG 파형·연속 혈압 기기 연동 검토", "지질 정식 채택, 웨어러블 단독 혈압 가능성", "6개월+"],
], [640, 2400, 3560, 2100, 938], { zebra: false });
callout("실사용 관문: ", `(1) 순위 1·2·4 완료 → 의료진 검토용 시범 적용 · (2) 정답지 30명 도달 + 웨어러블 기여가 ${HO}에서 유의 → 사용자 노출 · (3) 의료진 승인 → 병원 안내·가정방문 연계. 세 관문 전에는 예측값을 '참고 추정치'로만 표시합니다.`);
h1("11. 의사결정 요청 사항");
point("아래 4가지가 정해져야 10장 순위 1~3 작업을 시작할 수 있습니다.");
table(["번호", "요청", "왜 필요한가"], [
  ["1", "서비스 전환 방식 — 결합 방식(M1 + 웨어러블 변화분) vs 통합 모델 직접", "웨어러블 반영 산출의 형태·라벨링 결정 (순위 2)"],
  ["2", "검진 결과 업로드 캠페인 승인 (대상 180명)", "정답지 없이는 웨어러블 기여 검증 불가 (순위 3)"],
  ["3", "의료진 검토 파일럿 지정 (임계값·변화 기준폭 승인 주체)", "임상 기준·병원 연계 규칙 확정 (순위 6)"],
  ["4", "고위험 영역 표시 방식 (구간 상한 / 플래그 우선 / 보류)", "과소예측 결함의 화면 처리 원칙 (순위 1)"],
], [700, 5200, 3738]);
ch.push(P([], { spacing: { after: 120 } }));
src(`근거 파일: 01_Results/model_audit.json · significance.json · configs/*_rules.json · serving/m1_predictions_2026-09-10.parquet(가명키). 한계: 모든 성능은 ${HO} 59명 기준이며 M0·웨어러블 반영 예측은 미검증. 본 모델은 진단·치료가 아닌 검진·진료 안내 보조 도구입니다.`);

const footer = new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: TW }], children: [
  new TextRun({ text: "건강검진 예측 모델 분석 보고서 · 헬스커넥트(주) · 대외비", color: C.gray, size: 16 }), new TextRun({ text: "\t", color: C.gray, size: 16 }), new TextRun({ children: [PageNumber.CURRENT], color: C.gray, size: 16 })] })] });
const doc = new Document({
  styles: { default: { document: { run: { font: "Pretendard", color: C.text, size: 20 } } }, paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Pretendard", bold: true, color: C.navy, size: 28 }, paragraph: { outlineLevel: 0 } }] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "●", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } }, run: { color: C.gray, size: 12 } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134, header: 708, footer: 708 } } }, footers: { default: footer }, children: ch }],
});
Packer.toBuffer(doc).then(buf => { const out = "/Users/jaeho.oh/Downloads/SiBC_건강검진예측모델_분석보고서_20260917.docx"; fs.writeFileSync(out, buf); console.log("written", out, buf.length); });
