// 모델 분석 보고서 v2 — "푸드렌즈 RAG 활용방안 보고서" 템플릿 포맷(A4, Pretendard, 표지/EXEC SUMMARY/PART/장, 진청 표, 파란 강조상자, 시각화 그리드)
const fs = require("fs"), path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, AlignmentType, BorderStyle, ShadingType, HeadingLevel, LevelFormat, ImageRun, Footer, PageNumber, TabStopType, PageBreak, VerticalAlign } = require("docx");
const ROOT = path.join(__dirname, ".."), ASSETS = path.join(__dirname, "report_assets");
const audit = JSON.parse(fs.readFileSync(path.join(ROOT, "01_Results/model_audit.json"), "utf8"));
const sig = JSON.parse(fs.readFileSync(path.join(ROOT, "01_Results/significance.json"), "utf8"));
const C = { navy: "0A3D9A", blue: "0A64FC", gray: "6B7280", text: "111827", red: "D92D20", line: "E5E7EB", zebra: "F8FAFC", amber: "FEF3C7", pale: "F1F5FF", green: "15803D" };
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" }, LINE = { style: BorderStyle.SINGLE, size: 4, color: C.line };
const ch = [];
const R = (t, o = {}) => new TextRun({ text: t, bold: !!o.bold, color: o.color, size: o.size });
const P = (runs, o = {}) => new Paragraph({ spacing: Object.assign({ after: 110, line: 295, lineRule: "auto" }, o.spacing || {}), keepNext: o.keepNext, pageBreakBefore: o.pageBreakBefore, alignment: o.align, children: runs });
const body = (t, o) => ch.push(P(typeof t === "string" ? [R(t)] : t, o));
const partHead = (label, title, sub) => { ch.push(P([R(label, { bold: true, color: C.blue, size: 24 })], { spacing: { before: 100, after: 80 }, pageBreakBefore: true })); ch.push(P([R(title, { bold: true, size: 32 })], { spacing: { after: 120 } })); ch.push(P([R(sub, { color: C.gray, size: 22 })], { spacing: { after: 200 } })); };
const h1 = t => ch.push(new Paragraph({ heading: HeadingLevel.HEADING_1, keepNext: true, spacing: { before: 320, after: 140 }, children: [R(t, { bold: true, color: C.navy, size: 28 })] }));
const bullet = (lead, t) => ch.push(new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 65, line: 280, lineRule: "auto" }, children: lead ? [R(lead + " ", { bold: true }), R(t)] : [R(t)] }));
const src = t => ch.push(P([R("자료: " + t, { color: C.gray, size: 18 })]));
function callout(lead, t, fill = C.pale, bar = C.blue, bold = true) {
  ch.push(new Table({ width: { size: 9638, type: WidthType.DXA }, columnWidths: [9638], borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: [new TableRow({ children: [new TableCell({ width: { size: 9638, type: WidthType.DXA }, shading: { type: ShadingType.CLEAR, fill }, borders: { top: NONE, bottom: NONE, right: NONE, left: { style: BorderStyle.SINGLE, size: 24, color: bar } },
      margins: { top: 108, bottom: 108, left: 150, right: 150 }, children: [new Paragraph({ spacing: { line: 285, lineRule: "auto" }, children: [R(lead, { bold: true, color: bar }), R(t, { bold, color: bar === C.blue ? C.navy : C.text })] })] })] })] }));
  ch.push(P([], { spacing: { after: 60 } }));
}
function table(header, rows, widths, opts = {}) {
  const total = 9638, sc = total / widths.reduce((a, b) => a + b, 0), W = widths.map(w => Math.round(w * sc)); W[W.length - 1] += total - W.reduce((a, b) => a + b, 0);
  const cell = (t, w, head, fill) => new TableCell({ width: { size: w, type: WidthType.DXA }, borders: { top: LINE, bottom: LINE, left: LINE, right: LINE }, margins: { top: 78, bottom: 78, left: 100, right: 100 },
    shading: { type: ShadingType.CLEAR, fill: head ? C.navy : (fill || "FFFFFF") }, verticalAlign: VerticalAlign.CENTER,
    children: [new Paragraph({ spacing: { after: 18, line: 250, lineRule: "auto" }, children: [R(String(t), { bold: head, color: head ? "FFFFFF" : C.text, size: 18 })] })] });
  ch.push(new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: W, layout: "fixed", borders: { top: LINE, bottom: LINE, left: LINE, right: LINE, insideHorizontal: LINE, insideVertical: LINE },
    rows: [new TableRow({ tableHeader: true, children: header.map((t, i) => cell(t, W[i], true)) }),
      ...rows.map((r, ri) => new TableRow({ cantSplit: true, children: r.map((t, i) => cell(t, W[i], false, r.__fill || ((opts.zebra !== false && ri % 2 === 1) ? C.zebra : undefined))) }))] }));
  ch.push(P([], { spacing: { after: 120 } }));
}
const hl = (a, f = C.amber) => { a.__fill = f; return a; };
const img = (file, w = 2933700, h = 1676400) => new Paragraph({ alignment: AlignmentType.CENTER, children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(ASSETS, file)), transformation: { width: Math.round(w / 9525), height: Math.round(h / 9525) } })] });
function vizFull(title, file, caption) {
  ch.push(P([R(title, { bold: true, color: C.navy, size: 22 })], { keepNext: true, spacing: { before: 120, after: 60 } }));
  ch.push(new Paragraph({ keepNext: true, alignment: AlignmentType.CENTER, children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(ASSETS, file)), transformation: { width: 643, height: 367 } })] }));
  ch.push(P([R(caption, { color: C.gray, size: 17 })], { spacing: { before: 60, after: 200 } }));
}
function vizGrid(title, files, caption) {
  ch.push(P([R(title, { bold: true, color: C.navy, size: 22 })], { keepNext: true, spacing: { after: 80 } }));
  const cell = f => new TableCell({ width: { size: 4819, type: WidthType.DXA }, borders: { top: NONE, bottom: NONE, left: NONE, right: NONE }, margins: { top: 40, bottom: 40, left: 40, right: 40 }, children: [img(f)] });
  const rows = []; for (let i = 0; i < files.length; i += 2) rows.push(new TableRow({ cantSplit: true, children: [cell(files[i]), cell(files[i + 1] || files[i])] }));
  ch.push(new Table({ width: { size: 9638, type: WidthType.DXA }, columnWidths: [4819, 4819], borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE }, rows }));
  ch.push(P([R(caption, { color: C.gray, size: 17 })], { spacing: { before: 80, after: 200 } }));
}
const m1 = sig.m1, clf = sig.clf, sub = audit.subgroup, srv = audit.serving;

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
bullet("어디까지 쓸 수 있는가.", `검진 이력이 있는 사용자의 다음 혈압·공복혈당 예측과 비만·복부비만 플래그는 우리 사용자 봉인 테스트(59명)에서 '직전 검진값 그대로'보다 통계적으로 유의하게 정확했습니다(수축기 ${m1.sbp.mae_cf}→${m1.sbp.mae_model} mmHg, 공복혈당 ${m1.fasting_glucose.mae_cf}→${m1.fasting_glucose.mae_model} mg/dL). 의료진 검토용 시범 적용이 가능한 수준입니다.`);
bullet("무엇이 아직인가.", "프로젝트의 핵심 목적인 '웨어러블을 반영한 예측'과 '검진 이력 없는 사용자의 유사 검진값'은 검증되지 않았습니다. 서빙 중인 모델의 입력에 웨어러블 특징이 0개이고, 검증에 필요한 '웨어러블 착용 뒤 받은 검진' 정답지가 15건(12명)뿐이기 때문입니다.");
bullet("가장 위험한 결함은 무엇인가.", `모델이 고위험 영역에서 낮게 예측합니다. 실제 수축기 ≥140인 사람을 평균 ${Math.abs(sub.sbp.high_range.bias)} mmHg, 공복혈당 ≥126인 사람을 ${Math.abs(sub.fasting_glucose.high_range.bias)} mg/dL 낮게 봅니다. '병원에 가야 할 사람을 정상처럼 보이게' 하는 방향이라, 예측값만으로 병원 안내를 판단해서는 안 됩니다.`);
bullet("구축 방법은 적정한가.", "시간 누출 방지·사용자 단위 봉인·사전 승격 규칙·강한 기준선·부트스트랩 신뢰구간·데이터 계보는 갖춰져 있습니다. 빠진 것은 웨어러블 특징 반영, 고위험 과소예측 보정, 한국인 보정의 서빙 적용, 시간 분할 검증, 드리프트 감시입니다.");
callout("시사점: ", "현재 모델은 '검진 이력이 있는 사용자'를 위한 개인화 추정·위험 플래그 도구로는 의료진 검토 단계에 들어갈 수 있지만, 사용자에게 직접 노출하거나 웨어러블 기반 예측을 주장할 단계는 아닙니다. 성능을 올리는 지렛대는 모델 기법이 아니라 '착용 뒤 검진' 정답지의 확보이며, 실사용 전에는 고위험 과소예측 보정이 선행되어야 합니다.");
src("자체 데이터 봉인 테스트(사용자 59명, 1회 평가, m1_v3·clinical), 2026-09-17 추가 감사(scripts/audit_model.py: 서빙 커버리지·특징 의존·하위집단 편향·시드 안정성), 사용자 클러스터 부트스트랩(B=2,000). 사용자 식별 정보는 사용하지 않았습니다.");

// ================= PART I =================
partHead("PART I", "지금 어디까지 왔는가", "무엇을 맞히는 모델이고, 어떤 데이터로 어떻게 만들었으며, 항목별로 어디까지 쓸 수 있는지 판정합니다.");
h1("1. 모델이 하는 일 — 과거 웨어러블과 검진으로 '오늘 검진하면 나올 값'을 추정");
body("이 모델은 사용자의 예측 시점 이전 데이터(직전 검진값, 그 이후 누적된 웨어러블 요약, 성별·연령)로 검진 항목 10종(혈압 2, 신체계측 3, 공복혈당, 지질 4)의 현재 값을 추정합니다. 검진 이력이 있으면 개인화 경로(M1), 없으면 웨어러블 전용 경로(M0)를 씁니다. 출력은 예측값과 85% 구간, 기준 초과 확률(플래그), 변화 방향이며, 근거가 부족하면 '보류(ABSTAIN)'와 사유를 냅니다.");
table(["용어", "쉬운 설명"], [
  ["M1 (개인화)", "직전 검진값을 개인 기준선으로 두고 다음 검진값을 추정. 현재 검증된 서비스 경로"],
  ["M0 (웨어러블 전용)", "검진 이력 없이 웨어러블·인구통계만으로 추정. 공공데이터로 학습만 됨, 우리 사용자 검증 전"],
  ["봉인 테스트", "사용자 20%(59명)를 떼어 두고 마지막에 1회만 평가. 모든 성능 수치의 출처"],
  ["직전값 그대로 (carry-forward)", "'다음 검진도 지난번과 같다'는 가장 강한 기준선. 이를 못 이기면 모델 가치 없음"],
  ["MAE / AUROC", "평균절대오차(낮을수록 정확) / 판별력(0.5 동전 던지기, 0.8 이상 양호, 0.9 이상 우수)"],
  ["정답지 (forward 쌍)", "웨어러블이 쌓인 '뒤에' 받은 검진. 웨어러블→검진 관계를 배우고 검증하는 데 필요한 예시"],
], [2400, 7238]);
h1("2. 구축 방법 한눈에");
table(["단계", "무엇을 했나", "결과"], [
  ["1. 데이터 통합", "공공(NHANES 미국 9,981 · KNHANES 한국 592) + 자체 검진 1,549건(394명)을 한 테이블로, 출처 표시·가중치", "12,122행. 공공은 학습에만, 평가에는 0행"],
  ["2. 알고리즘 파일럿", "5개 후보(선형·랜덤포레스트·부스팅·MLP·혼합효과)를 사용자 단위 5회 교차검증으로 항목별 비교", "부스팅 5/10 1위 → 주 알고리즘, 항목별 최적 혼용"],
  ["3. 학습·튜닝", "통합 모델 v1.3, 개인화 M1 v3(혼합효과·CQR 구간·교차특징), 임상 판별 모델", "10항목 모델 + 플래그 4종 + 방향 2종"],
  ["4. 봉인 검증", "사전 승격 규칙(직전값 대비 ≥3% 개선·과반 폴드 승·학습 100명/봉인 30명)", "혈압·혈당 승격, 체중·BMI 직전값 유지, 지질 교차 모델"],
  ["5. 서비스 산출", "사용자당 1행: 실제값·측정 요약·예측·구간·플래그·방향·보류 사유", "394명 산출, 구간 위반 0건, 가명키만"],
], [2000, 4600, 3038]);
vizFull("시각화 E — 학습 데이터 구성과 웨어러블 검증의 병목", "E_data.png", "왼쪽: 통합 학습 테이블의 출처별 행 수(공공은 학습에만 사용). 오른쪽: 웨어러블→검진 검증에 쓸 수 있는 정답지 12명 대 정책 게이트 30명, 그리고 현재 M1이 학습한 검진 쌍 292명.");
h1("3. 항목별 실사용 준비도 판정");
table(["판정", "항목", "근거"], [
  hl(["제한적 사용 가능 (의료진 검토용)", "혈압(수축·이완)·공복혈당 개인화 예측, 비만·복부비만 플래그", "봉인셋에서 직전값보다 유의하게 정확(95% CI 전체 개선), 시드 3종 모두 승격 안정. 단 고위험 과소예측 때문에 회귀값 단독 병원 안내 금지"], "E8F5E9"),
  hl(["참고용 (사용자 노출 비권장)", "고혈압·공복혈당장애 플래그, 지질 4항목, 변화 방향", "판별력 양호(AUROC 0.82)이나 기준선 대비 개선 신뢰구간이 0 포함. 지질 R² 0.07~0.21"], C.amber),
  hl(["직전값 유지 (모델 가치 없음)", "체중·BMI·허리둘레", "직전값 자체 R² 0.95/0.91. 웨어러블 체중계 측정값이 더 유용"], C.zebra),
  hl(["사용 불가 (미검증)", "검진 이력 없는 사용자의 웨어러블 전용 예측(M0)", "검증 쌍 15건/12명 < 게이트 30명"], "FDECEA"),
  hl(["목적 미충족 (핵심 갭)", "검진 이력 보유자의 '웨어러블 반영' 예측", "서빙 M1의 입력 특징에 웨어러블 관측창 0개 (정답지 부족으로 자동 제외)"], "FDECEA"),
], [2300, 2900, 4438], { zebra: false });
callout("한 줄 판정: ", "'검진 이력이 있는 사용자의 다음 혈압·혈당을 직전값보다 정확히 추정하고 기준 초과를 플래그하는 도구'로는 의료진 검토용 시범 적용이 가능합니다. 웨어러블 반영·이력 없는 사용자 예측은 아직 검증 전입니다.");
vizFull("시각화 A — 항목별 실사용 준비도", "A_readiness.png", "초록: 제한적 사용 가능 · 주황: 참고용 · 회색: 직전값 유지 · 빨강: 미검증 또는 목적 미충족. 오른쪽으로 갈수록 실사용에 가깝습니다.");

// ================= PART II =================
partHead("PART II", "성능은 객관적으로 어느 수준인가", "우리 사용자 봉인 테스트 결과를 기준선·신뢰구간과 함께 보고, 감사에서 새로 드러난 결함을 짚습니다.");
h1("4. 개인화 예측(M1) — 직전값보다 얼마나 정확한가");
body(`혈압·공복혈당은 '직전 검진값 그대로'보다 14~20% 오차가 줄었고, 사용자 단위 부트스트랩 95% 신뢰구간이 전부 개선 쪽에 있어 통계적으로 유의합니다. 봉인 분할 시드를 3종으로 바꿔도 승격 결과가 동일해 우연이 아닙니다. 체중·BMI는 직전값이 이미 R² 0.95/0.91로 정확해 모델을 쓰지 않는 것이 옳다는 결론이 안정적으로 재현됐습니다.`);
table(["항목", "서빙 경로", "봉인 MAE: 모델 vs 직전값", "개선 (95% CI)", "R²", "시드 3종"], [
  ["수축기혈압", "모델(선형)", `${m1.sbp.mae_model} vs ${m1.sbp.mae_cf}`, `${m1.sbp.diff} [${m1.sbp.diff_ci95}]`, "0.31", "MODEL ×3"],
  ["이완기혈압", "모델(혼합효과)", `${m1.dbp.mae_model} vs ${m1.dbp.mae_cf}`, `${m1.dbp.diff} [${m1.dbp.diff_ci95}]`, "0.24", "MODEL ×3"],
  ["공복혈당", "모델(혼합효과)", `${m1.fasting_glucose.mae_model} vs ${m1.fasting_glucose.mae_cf}`, `${m1.fasting_glucose.diff} [${m1.fasting_glucose.diff_ci95}]`, "0.17", "MODEL ×3"],
  ["체중 · BMI", "직전값 유지", "직전값 R² 0.95 / 0.91", "개선 3% 미달", "—", "CF ×3"],
  ["허리둘레", "직전값 유지", "직전값 MAE 3.9 cm", "—", "—", "—"],
  ["지질 4항목", "교차특징 모델", "이력 없어도 약 310명 예측", "모집단 평균 대비 ≥3%", "0.07~0.21", "—"],
], [1250, 1400, 1950, 2000, 1300, 1738]);
vizFull("시각화 B — 개인화 예측 정확도 (봉인 테스트, 사용자 59명)", "B_m1_mae.png", "연청: 직전 검진값 그대로, 진청: 우리 모델(M1). 초록 글씨는 오차 감소폭과 95% 신뢰구간 — 구간 전체가 음수이면 개선이 통계적으로 유의합니다.");
h1("5. 기준 초과 판별 — '다음 검진에서 기준을 넘는가'");
body("정확한 수치보다 서비스가 실제로 묻는 '기준을 넘는가'는 훨씬 잘 맞힙니다. 네 문제 모두 직전 상태 유지 기준선보다 높았지만, 신뢰구간으로 보면 비만·복부비만만 개선이 확정이고 고혈압·혈당장애는 표본이 더 필요합니다.");
table(["문제", "AUROC (95% CI)", "직전 상태 기준선", "개선 (95% CI)", "판정"], [
  ["고혈압 ≥140/90", `${clf.hypertension_140_90.auroc} [${clf.hypertension_140_90.auroc_ci95}]`, `${clf.hypertension_140_90.prior_auroc}`, `${clf.hypertension_140_90.diff_vs_prior} [${clf.hypertension_140_90.diff_ci95}]`, "판별력 양호, 개선 미확정"],
  ["공복혈당장애 ≥100", `${clf.fasting_glucose_ge100.auroc} [${clf.fasting_glucose_ge100.auroc_ci95}]`, `${clf.fasting_glucose_ge100.prior_auroc}`, `${clf.fasting_glucose_ge100.diff_vs_prior} [${clf.fasting_glucose_ge100.diff_ci95}]`, "경계"],
  hl(["비만 BMI≥25", `${clf.obesity_bmi_ge25.auroc} [${clf.obesity_bmi_ge25.auroc_ci95}]`, `${clf.obesity_bmi_ge25.prior_auroc}`, `${clf.obesity_bmi_ge25.diff_vs_prior} [${clf.obesity_bmi_ge25.diff_ci95}]`, "개선 유의"], "E8F5E9"),
  hl(["복부비만", `${clf.abdominal_obesity.auroc} [${clf.abdominal_obesity.auroc_ci95}]`, `${clf.abdominal_obesity.prior_auroc}`, `${clf.abdominal_obesity.diff_vs_prior} [${clf.abdominal_obesity.diff_ci95}]`, "개선 유의"], "E8F5E9"),
  ["고중성지방 ≥150", "—", "—", "—", "양성 8건, 정책상 보류"],
], [1900, 2200, 1500, 2200, 1838], { zebra: false });
vizFull("시각화 C — 기준 초과 판별력 (봉인 테스트)", "C_auroc.png", "연청: 직전 상태 유지 기준선, 진청: 우리 모델, 오차막대: 95% 신뢰구간. 하단 라벨은 기준선 대비 개선이 통계적으로 확정됐는지(유의/미확정)를 뜻합니다.");
h1("6. 감사에서 드러난 결함 — 고위험 영역 과소예측");
body(`성별·연령·직전 검진 경과일로 나누면 편향이 ±5 이내이고 모든 구간에서 직전값보다 정확합니다. 그러나 실제값이 임상 기준을 넘는 고위험 영역에서는 크게 낮게 예측합니다. 혼합효과·선형 모델이 개인 값을 모집단 평균 쪽으로 끌어당기는(축소) 특성 때문이며, '병원에 가야 할 사람을 정상처럼 보이게' 하는 방향이라 서비스 목적에 가장 위험한 오류입니다.`);
table(["항목", "구간", "n", "편향(예측−실제)", "모델 MAE"], [
  hl(["수축기혈압", "실제 ≥140 (고혈압 영역)", `${sub.sbp.high_range.n}`, `${sub.sbp.high_range.bias}`, `${sub.sbp.high_range.mae}`], "FDECEA"),
  ["", "남성 / 여성", `${sub.sbp.sex["1.0"].n} / ${sub.sbp.sex["2.0"].n}`, `${sub.sbp.sex["1.0"].bias} / ${sub.sbp.sex["2.0"].bias}`, `${sub.sbp.sex["1.0"].mae} / ${sub.sbp.sex["2.0"].mae}`],
  hl(["이완기혈압", "실제 ≥90", `${sub.dbp.high_range.n}`, `${sub.dbp.high_range.bias}`, `${sub.dbp.high_range.mae}`], "FDECEA"),
  hl(["공복혈당", "실제 ≥126 (당뇨 영역)", `${sub.fasting_glucose.high_range.n}`, `${sub.fasting_glucose.high_range.bias}`, `${sub.fasting_glucose.high_range.mae}`], "FDECEA"),
  ["", "남성 / 여성", `${sub.fasting_glucose.sex["1.0"].n} / ${sub.fasting_glucose.sex["2.0"].n}`, `${sub.fasting_glucose.sex["1.0"].bias} / ${sub.fasting_glucose.sex["2.0"].bias}`, `${sub.fasting_glucose.sex["1.0"].mae} / ${sub.fasting_glucose.sex["2.0"].mae}`],
], [1500, 3000, 1300, 2000, 1838], { zebra: false });
vizFull("시각화 D — 고위험 영역 과소예측", "D_bias.png", "편향 = 예측 − 실제. 연청(전체)은 ±3 이내지만 빨강(실제값이 임상 기준을 넘는 고위험 영역)은 크게 음수 — 위험한 사람을 낮게 예측합니다. 괄호는 해당 영역 표본 수.");
callout("핵심: ", "회귀 예측값을 단독으로 병원 안내 근거로 쓰면 안 됩니다. 기준 초과 플래그(분류 모델)는 고위험 영역을 별도로 학습하므로 반드시 병행하고, 실사용 전에 고위험 구간 보정(보완 순위 1)을 완료해야 합니다.", C.amber, "D97706", false);
h1("7. 서빙 모델은 웨어러블을 보지 않는다 — 핵심 목적과의 갭");
body("퍼뮤테이션 중요도(봉인셋에서 특징을 섞었을 때 오차 증가량)로 서빙 모델이 실제로 의존하는 특징을 확인했습니다. 세 모델 모두 '직전값 · 직전-직전값 · 연령'에 의존하고, 웨어러블 관측창 특징은 입력에 존재하지 않습니다. 이유는 웨어러블 수집이 2025-12에 시작돼 '웨어러블 뒤 검진' 학습 예시가 15건(전체의 1.4%)뿐이고, 커버리지 5% 미만 특징이 자동 제외되기 때문입니다.");
table(["모델", "1위 (MAE 증가)", "2위", "3위", "웨어러블 특징"], [
  ["수축기혈압", "직전 수축기 (+1.30)", "직전-직전 수축기 (+0.45)", "연령 (+0.28)", "0개"],
  ["이완기혈압", "직전 이완기 (+1.18)", "직전-직전 이완기 (+0.51)", "성별 (+0.12)", "0개"],
  ["공복혈당", "직전 혈당 (+3.76)", "직전-직전 혈당 (+2.44)", "연령 (+0.11)", "0개"],
], [1600, 2400, 2400, 1600, 1638]);
body("설계상 서빙은 '마지막 검진 + 그 이후 웨어러블'을 그대로 조립하므로 원래 목적(검진 이후 누적 웨어러블 활용)과 어긋나지 않습니다. 어긋난 곳은 학습입니다 — 웨어러블 패턴이 검진값과 어떻게 연결되는지 배우려면 웨어러블 뒤에 실제 검진(정답지)이 있어야 하는데 그 예시가 부족합니다. 웨어러블·활동 특징 4개를 포함한 통합 모델 v1.3을 정답지 15건에 적용하면 이완기 4.67 vs 직전값 6.71, 공복혈당 8.41 vs 13.0으로 유리한 방향이 보이지만, 표본이 작아 성능 주장에는 쓸 수 없습니다.");
h1("8. 서비스 산출 커버리지");
body(`394명 산출에서 혈압·공복혈당은 320~323명(82%)에 예측을 제공하고 71~74명은 보류합니다(검진 이력 없음 ${srv.abstain_reasons_sbp.no_prior_checkup}, 직전 검진 3년 초과 ${srv.abstain_reasons_sbp.stale_anchor}). 지질은 교차 모델로 보류가 1명까지 줄었습니다. 웨어러블 충분성은 A등급(30일 중 21일 이상) 183명(46%), 미착용 136명(35%)으로, 사용자의 1/3은 웨어러블 경로가 검증돼도 적용 대상이 아닙니다.`);
vizFull("시각화 F — 서비스 산출 커버리지 (394명)", "F_coverage.png", "항목별 서빙 경로: 진청 모델 예측 · 파랑 교차 모델(참고) · 연청 직전값 유지 · 회색 보류. 막대 안 숫자는 사용자 수.");

// ================= PART III =================
partHead("PART III", "무엇을 보완해야 하는가", "구축 방법에서 빠진 것, 우선순위, 그리고 실사용 관문입니다.");
h1("9. 구축 방법 평가 — 갖춰진 것");
table(["항목", "구현 상태", "평가"], [
  ["시간 누출 방지", "검진일 이전 데이터만 사용, 계약 테스트로 강제", "적정 — 임베딩 부여 시에도 관측창 보유 행에만 제한"],
  ["평가 설계", "사용자 단위 봉인 20% + GroupKFold(5), 봉인셋 미참조 사전 승격 규칙", "적정 — 소표본 착시(지질 봉인 R² −1.4)를 정책 게이트가 차단한 실적"],
  ["기준선", "직전값 유지, 모집단 평균, 직전 상태 유지", "적정 — 임상 예측에서 가장 강한 기준선 포함"],
  ["통계적 유의성", "사용자 클러스터 부트스트랩(B=2,000) 95% CI", "적정 — 반복 측정 상관 반영"],
  ["재현성·계보", "schema 앵커링, model_registry, 규칙 파일, 시드 3종 안정성", "적정 — '검증·완성은 자체 데이터' 증거 사슬"],
  ["불확실성", "잔차 분위수 + CQR, 봉인 PICP 0.80~0.93", "적정 — 명목 85% 구간이 실제로 담김"],
], [1900, 4100, 3638]);
h1("10. 구축 방법 평가 — 빠진 것");
table(["#", "부족한 부분", "왜 문제인가", "심각도"], [
  hl(["1", "웨어러블 특징이 서빙 모델에 없음", "정답지 15건 → 자동 제외. 프로젝트 목적과 직접 충돌", "치명"], "FDECEA"),
  hl(["2", "고위험 영역 과소예측 미보정", "수축기≥140 −13, 혈당≥126 −36. 병원 안내에 가장 위험한 오류 방향", "치명"], "FDECEA"),
  hl(["3", "한국인 보정(calibration) 서빙 미적용", "KNHANES 기준표는 있으나 서빙에 미연결. 미국 데이터 82% 통합 모델 서빙 시 필수", "높음"], C.amber),
  hl(["4", "시간 분할 검증 부재", "봉인은 사용자 분할. '과거로 학습해 미래 예측' 재현성은 정답지 15건으로만 확인", "높음"], C.amber),
  ["5", "드리프트 감시·재학습 자동화 없음", "기기·사용자 구성 변화 시 성능 저하를 감지할 장치 없음", "중간"],
  ["6", "봉인셋 59명 — 신뢰구간 넓음", "하위집단(연령대 21~67명) 결론 불안정", "중간"],
  ["7", "임상 임계값·변화 τ 의료진 검토 미실시", "문헌 기준. 서비스 맥락(중국 가정방문)의 승인 필요", "중간"],
  ["8", "자기지도 임베딩·대리 학습 미활용", "현 신호·표본에서 기여 없음(임베딩 과적합, 심박→혈압 R²≈0)", "낮음"],
], [500, 2800, 5000, 1338], { zebra: false });
h1("11. 보완 우선순위와 실사용 관문");
table(["순위", "과제", "방법", "효과", "기간"], [
  hl(["1", "고위험 과소예측 보정", "플래그 양성 시 구간 상한 표시, 고위험 가중(분위수 0.75) 보조 모델, 극단값 잔차 보정표", "병원 안내 누락 위험 제거 — 실사용 전제", "1~2주"], "FDECEA"),
  hl(["2", "웨어러블 반영 서빙 (하이브리드)", "검증된 M1 기본 + 통합 모델의 웨어러블 변화분, '참고 추정치' 라벨. 이력 없는 사용자는 M0 유사 검진값", "핵심 목적 충족(검증 전 참고용)", "2주"], "FDECEA"),
  hl(["3", "'착용 뒤 검진' 정답지 캠페인", "연례 검진자 180명 업로드 유도, 자동 평가로 30명 도달 추적", "웨어러블 기여 검증의 유일한 경로", "3~6개월"], "FDECEA"),
  hl(["4", "한국인 보정 서빙 적용", "KNHANES 성별×연령대 기준표를 통합 모델 출력에 분위수 정합", "미국 데이터 편향 제거", "1주"], C.amber),
  hl(["5", "시간 분할 검증", "2025년 이전 학습 → 2025~2026 검진 평가 폴드", "미래 예측 재현성 확인", "1주"], C.amber),
  hl(["6", "의료진 검토 파일럿", "예측·구간·플래그·방향 검토 화면, 임계값·τ 승인, 피드백 라벨", "임상 타당성·규칙 확정", "1~2개월"], C.amber),
  ["7", "모니터링·재학습 자동화", "드리프트·PICP·양성률 대시보드, 분기 재학습, 계보 자동 기록", "운영 안정성", "2~3주"],
  ["8", "지질·고TG 라벨 축적", "반복 지질 검진 업로드 후 개인화·판별 재시도", "지질 정식 승격", "6개월+"],
  ["9", "새 신호 확보 검토", "PPG 파형·연속 혈압 기기 연동(현 채널로는 혈압 복원 불가 확인)", "웨어러블 단독 혈압 가능성", "탐색"],
], [500, 2200, 3700, 2200, 1038], { zebra: false });
callout("실사용 관문: ", "(1) 순위 1·2·4 완료 → 의료진 검토용 시범 적용 · (2) 정답지 30명 도달 + 웨어러블 기여가 봉인셋에서 유의 → 사용자 노출 · (3) 의료진 승인 → 병원 안내·가정방문 연계. 세 관문 전에는 예측값을 '참고 추정치'로만 표시합니다.");
h1("12. 의사결정 요청 사항");
table(["번호", "요청", "왜 필요한가"], [
  ["1", "서빙 전환 방식 선택 — 하이브리드(M1 기본+웨어러블 변화분) vs 통합 모델 직접", "웨어러블 반영·이력 없는 사용자 산출의 형태와 라벨링이 정해집니다"],
  ["2", "검진 결과 업로드 캠페인 승인 (대상 180명, 앱 알림·현장 안내)", "정답지 없이는 웨어러블 기여를 검증할 수 없습니다"],
  ["3", "의료진 검토 파일럿 지정 (임계값·변화 τ 승인 주체)", "플래그·방향의 임상 기준과 병원 연계 규칙이 확정됩니다"],
  ["4", "고위험 영역 표시 방식 (구간 상한 노출 / 플래그 우선 / 보류)", "과소예측 결함의 화면 처리 원칙이 필요합니다"],
], [800, 4800, 4038]);
h1("부록. 감사 방법과 근거 파일");
bullet("", "감사: scripts/audit_model.py → 01_Results/model_audit.json (서빙 커버리지, 퍼뮤테이션 중요도 20회 반복, 하위집단 잔차, 통합 모델 정답지 적용, 시드 42/7/2024 승격 안정성)");
bullet("", "유의성: scripts/significance.py → 01_Results/significance.json (사용자 클러스터 부트스트랩 B=2,000)");
bullet("", "모델·규칙: 01_Results/m1/m1_v3/, configs/m1_serving_rules.json, configs/clinical_rules.json, 01_Results/v1.3/ · 서빙 산출: 01_Results/serving/m1_predictions_2026-09-10.parquet (394명×101컬럼, 가명키)");
bullet("", "시각화: scripts/make_analysis_charts.py → scripts/report_assets/ (A~F, 1400×800) · 계약 테스트 27개 통과 · DB 규모(2026-09-17): 검진 525명, 웨어러블 513명");
bullet("", "한계 고지: 모든 성능은 봉인셋 59명 기준이며 웨어러블 전용(M0)·웨어러블 반영 예측의 정확도는 검증되지 않았습니다. 본 모델은 의료 진단·치료가 아닌 검진·진료 안내 보조 도구입니다.");

const footer = new Footer({ children: [new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: 9638 }], children: [
  new TextRun({ text: "건강검진 예측 모델 분석 보고서 · 헬스커넥트(주) · 대외비", color: C.gray, size: 16 }), new TextRun({ text: "\t", color: C.gray, size: 16 }), new TextRun({ children: [PageNumber.CURRENT], color: C.gray, size: 16 })] })] });
const doc = new Document({
  styles: { default: { document: { run: { font: "Pretendard", color: C.text, size: 20 } } }, paragraphStyles: [{ id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: "Pretendard", bold: true, color: C.navy, size: 28 }, paragraph: { outlineLevel: 0 } }] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "●", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 200 } }, run: { color: C.gray, size: 12 } } }] }] },
  sections: [{ properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, right: 1134, bottom: 1134, left: 1134, header: 708, footer: 708 } } }, footers: { default: footer }, children: ch }],
});
Packer.toBuffer(doc).then(buf => { const out = "/Users/jaeho.oh/Downloads/SiBC_건강검진예측모델_분석보고서_20260917.docx"; fs.writeFileSync(out, buf); console.log("written", out, buf.length); });
