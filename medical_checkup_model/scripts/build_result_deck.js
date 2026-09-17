// 건강검진 예측모델 구축·검증 결과 발표자료 — 템플릿(식이분석 리서치 발표자료) 포맷 준수
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5
pres.author = "오재호"; pres.company = "헬스커넥트(주) AI플랫폼본부 SiBC"; pres.title = "웨어러블 기반 건강검진 예측 모델 구축·검증 결과";

const C = { navy:"0A3D9A", blue:"0A64FC", light:"8FB4F5", pale:"F1F5FF", bg2:"F8FAFC", text:"1F2937", dark:"111827",
            gray:"6B7280", line:"E5E7EB", red:"D92D20", green:"15803D", orange:"C2410C", white:"FFFFFF", yellow:"FFF3B0" };
const F = { m:"Pretendard Medium", s:"Pretendard SemiBold", x:"Pretendard ExtraBold" };
const DECK = "건강검진 예측 모델 · 대외비";
const COVER_IMG = __dirname + "/deck_assets/cover.jpeg", LOGO = __dirname + "/deck_assets/logo.png";
let page = 0;

function footer(s){ page++;
  s.addText("서울 강서구 마곡중앙8로 38  |", {x:0.7,y:7.02,w:3,h:0.3,fontFace:F.m,fontSize:9,color:C.gray,isTextBox:true,margin:0});
  s.addText("COPYRIGHT @ 2024 Inviteseco INC. ALL RIGHTS RESERVED", {x:3.6,y:7.02,w:6,h:0.3,fontFace:F.m,fontSize:9,color:C.gray,align:"center",isTextBox:true,margin:0});
  s.addText(DECK, {x:9.6,y:7.02,w:2.9,h:0.3,fontFace:F.m,fontSize:9,color:C.gray,align:"right",isTextBox:true,margin:0});
  s.addText(String(page), {x:12.55,y:6.98,w:0.5,h:0.35,fontFace:F.m,fontSize:12,color:C.text,align:"right",isTextBox:true,margin:0});
}
function badge(s){ s.addShape(pres.ShapeType.roundRect,{x:11.82,y:0.22,w:1.36,h:0.42,rectRadius:0.06,fill:{color:C.white},line:{color:C.red,width:1}});
  s.addText("Confidential",{x:11.82,y:0.22,w:1.36,h:0.42,fontFace:F.m,fontSize:11,color:C.red,align:"center",valign:"middle",isTextBox:true,margin:0}); }
function header(s,label,h1,h2){ badge(s);
  s.addText(label,{x:0.62,y:0.42,w:10.5,h:0.3,fontFace:F.m,fontSize:12,color:C.blue,isTextBox:true,margin:0});
  s.addText([{text:h1,options:{breakLine:true}},{text:h2}],{x:0.62,y:0.74,w:11.2,h:1.0,fontFace:F.s,fontSize:22,color:C.dark,valign:"top",isTextBox:true,margin:0,lineSpacingMultiple:1.15});
  s.addShape(pres.ShapeType.line,{x:0.62,y:1.85,w:12.05,h:0,line:{color:C.line,width:1}}); }
function keyBox(s,text,y){ s.addShape(pres.ShapeType.rect,{x:0.75,y,w:11.9,h:0.5,fill:{color:C.pale},line:{color:C.pale}});
  s.addShape(pres.ShapeType.rect,{x:0.75,y,w:0.06,h:0.5,fill:{color:C.blue},line:{color:C.blue}});
  s.addText(text,{x:0.95,y,w:11.6,h:0.5,fontFace:F.m,fontSize:12.5,color:C.navy,valign:"middle",isTextBox:true,margin:0}); }
function source(s,text,y){ s.addText("자료: "+text,{x:0.62,y,w:12,h:0.28,fontFace:F.m,fontSize:9.5,color:C.gray,isTextBox:true,margin:0}); }
function card(s,x,y,w,h,title,color,lines){ s.addShape(pres.ShapeType.rect,{x,y,w,h,fill:{color:C.white},line:{color:C.line,width:1}});
  s.addText(title,{x:x+0.22,y:y+0.18,w:w-0.44,h:0.4,fontFace:F.s,fontSize:14,color,isTextBox:true,margin:0});
  s.addText(lines.map((t,i)=>({text:t,options:{breakLine:i<lines.length-1,paraSpaceAfter:6}})),{x:x+0.22,y:y+0.65,w:w-0.44,h:h-0.8,fontFace:F.m,fontSize:11.5,color:C.text,valign:"top",isTextBox:true,margin:0,lineSpacingMultiple:1.12}); }
function stat(s,x,y,w,big,label,color){ s.addText(big,{x,y,w,h:0.7,fontFace:F.x,fontSize:34,color,isTextBox:true,margin:0});
  s.addText(label,{x,y:y+0.72,w,h:0.5,fontFace:F.m,fontSize:11,color:C.gray,isTextBox:true,margin:0}); }
function table(s,rows,colW,x,y,opts={}){ const fs=opts.fontSize||11;
  const data=rows.map((r,i)=>r.map(c=>({text:String(c),options:i===0?{bold:true,color:C.white,fill:{color:C.navy},fontFace:F.m,fontSize:fs,valign:"middle"}
    :{color:C.text,fontFace:F.m,fontSize:fs,valign:"middle",fill:{color:(opts.hl&&opts.hl.includes(i))?C.yellow:C.white}}})));
  s.addTable(data,{x,y,w:colW.reduce((a,b)=>a+b,0),colW,border:{type:"solid",color:C.line,pt:0.75},rowH:opts.rowH||0.42,margin:[0.04,0.1,0.04,0.1]}); }
function divider(num,l1,l2,sub,active){ const s=pres.addSlide(); badge(s);
  s.addText(num,{x:0.62,y:1.2,w:3,h:1.2,fontFace:F.x,fontSize:60,color:C.blue,isTextBox:true,margin:0});
  s.addText([{text:l1,options:{breakLine:true}},{text:l2}],{x:0.62,y:2.55,w:11,h:1.4,fontFace:F.s,fontSize:30,color:C.dark,valign:"top",isTextBox:true,margin:0,lineSpacingMultiple:1.15});
  s.addText(sub,{x:0.62,y:3.95,w:11,h:0.5,fontFace:F.m,fontSize:15,color:C.gray,isTextBox:true,margin:0});
  ["01  모델은 어떻게 만들어졌나","02  성능은 어느 정도인가","03  무엇을 보완해야 하나"].forEach((t,i)=>{
    s.addText(t,{x:0.62,y:4.75+i*0.48,w:8,h:0.4,fontFace:i===active?F.s:F.m,fontSize:16,color:i===active?C.blue:C.text,isTextBox:true,margin:0}); });
  footer(s); return s; }
const chartBase = { chartColors:[C.navy,C.light], catAxisLabelColor:C.text, valAxisLabelColor:C.gray, catAxisLabelFontFace:F.m, valAxisLabelFontFace:F.m,
  catAxisLabelFontSize:10.5, valAxisLabelFontSize:9.5, valGridLine:{color:C.line,size:0.5}, catGridLine:{style:"none"}, dataLabelFontFace:F.m, dataLabelFontSize:9.5, dataLabelColor:C.text,
  legendFontFace:F.m, legendFontSize:10, legendColor:C.text, showTitle:false };

// ---------- 1. 표지 ----------
{ const s=pres.addSlide(); s.background={color:C.navy};
  s.addText("헬스커넥트(주) · AI플랫폼본부  SiBC",{x:1.0,y:0.55,w:8,h:0.4,fontFace:F.m,fontSize:14,color:C.white,isTextBox:true,margin:0});
  s.addText("대외비 · CONFIDENTIAL",{x:1.0,y:0.95,w:6,h:0.3,fontFace:F.m,fontSize:10,color:"FCA5A5",isTextBox:true,margin:0});
  if(fs.existsSync(LOGO)) s.addImage({path:LOGO,x:1.04,y:1.72,w:2.34,h:0.49});
  if(fs.existsSync(COVER_IMG)) s.addImage({path:COVER_IMG,x:5.6,y:2.86,w:7.73,h:4.64});
  s.addText("WEARABLE → HEALTH CHECKUP PREDICTION MODEL",{x:1.0,y:2.55,w:9,h:0.35,fontFace:F.m,fontSize:13,color:C.light,charSpacing:3,isTextBox:true,margin:0});
  s.addText("건강검진 예측 모델 구축·검증 결과",{x:1.0,y:2.95,w:9,h:0.8,fontFace:F.s,fontSize:34,color:C.white,isTextBox:true,margin:0});
  s.addText("웨어러블 데이터로 검진 항목을 예측하는 모델의 구조·알고리즘·성능 검증",{x:1.0,y:3.75,w:8.5,h:0.5,fontFace:F.m,fontSize:17,color:C.white,isTextBox:true,margin:0});
  s.addText([{text:"공공데이터와 자체 데이터를 하나의 모델로 학습하고, 모든 성능은 우리 사용자 봉인 테스트로 검증했습니다.",options:{breakLine:true}},{text:"무엇이 검증됐고 무엇이 아직인지를 처음 보는 분도 알 수 있도록 정리했습니다."}],
    {x:1.0,y:4.4,w:6.2,h:0.9,fontFace:F.m,fontSize:12.5,color:"DCE6FF",valign:"top",isTextBox:true,margin:0,lineSpacingMultiple:1.2});
  s.addText("오재호 과장",{x:1.0,y:5.45,w:4,h:0.45,fontFace:F.s,fontSize:18,color:C.white,isTextBox:true,margin:0});
  s.addText("AI플랫폼본부  SiBC",{x:1.0,y:5.92,w:4,h:0.35,fontFace:F.m,fontSize:11,color:C.light,isTextBox:true,margin:0});
  s.addText("서울 강서구 마곡중앙8로 38  |  COPYRIGHT @ 2024 Inviteseco INC. ALL RIGHTS RESERVED",{x:1.0,y:7.0,w:8,h:0.3,fontFace:F.m,fontSize:9,color:C.light,isTextBox:true,margin:0});
  page++; }

// ---------- 2. Executive Summary ----------
{ const s=pres.addSlide(); badge(s);
  s.addText("EXECUTIVE SUMMARY",{x:0.62,y:0.42,w:8,h:0.3,fontFace:F.m,fontSize:12,color:C.blue,isTextBox:true,margin:0});
  s.addText([{text:"혈압·공복혈당은 우리 사용자 데이터로 검증된 개인화 예측이 됩니다.",options:{breakLine:true}},{text:"웨어러블만으로 검진값을 맞히는 단계는 아직 아닙니다 — 라벨이 병목입니다."}],
    {x:0.62,y:0.74,w:12,h:1.0,fontFace:F.s,fontSize:22,color:C.dark,valign:"top",isTextBox:true,margin:0,lineSpacingMultiple:1.15});
  s.addShape(pres.ShapeType.line,{x:0.62,y:1.85,w:12.05,h:0,line:{color:C.line,width:1}});
  const items=[
   "1. 구축 — 공공데이터(NHANES·KNHANES 10,573명)와 자체 검진 1,549건(394명)을 한 테이블로 학습하는 통합 모델, 검진 이력 보유자용 개인화 모델(M1), 임계값 판별 모델, 사용자당 1행 서비스 산출까지 구현.",
   "2. 성능 — 봉인 테스트(사용자 59명)에서 수축기혈압 오차 10.8→8.8 mmHg, 이완기 8.1→7.0, 공복혈당 15.2→12.1 mg/dL로 '직전 검진값 그대로'보다 유의하게 정확(95% 신뢰구간 전체 개선). 비만·복부비만 판별 AUROC 0.96.",
   "3. 한계 — 웨어러블 착용 '후'에 받은 검진 쌍이 15건(12명)뿐이라 웨어러블 전용 예측(M0)은 검증 보류. 심박·수면·걸음만으로 혈압을 복원하는 것은 현 신호로는 불가(설명력 ≈0)함을 두 차례 확인."];
  s.addText(items.map((t,i)=>({text:t,options:{breakLine:i<2,paraSpaceAfter:14}})),{x:0.75,y:2.2,w:11.9,h:3.0,fontFace:F.m,fontSize:13,color:C.text,valign:"top",isTextBox:true,margin:0,lineSpacingMultiple:1.25});
  s.addShape(pres.ShapeType.rect,{x:0.75,y:5.45,w:11.9,h:0.8,fill:{color:C.pale},line:{color:"C7D7FF",width:1}});
  s.addText([{text:"시사점: ",options:{bold:true,color:C.blue}},{text:"지금 서비스 가능한 것은 '검진 이력이 있는 사용자'의 다음 검진 예측과 기준 초과 플래그입니다. 성능을 더 올리는 지렛대는 모델 기법이 아니라 검진 결과 업로드로 '착용 후 검진' 라벨을 늘리는 것입니다.",options:{color:C.navy}}],
    {x:0.95,y:5.45,w:11.5,h:0.8,fontFace:F.m,fontSize:12.5,valign:"middle",isTextBox:true,margin:0});
  source(s,"medical_checkup_model 구현 산출물(m1_v3, clinical, benchmark, serving) · 2026-09-10 기준 자체 봉인 테스트 결과.",6.4);
  footer(s); }

// ---------- 3. 섹션 01 ----------
divider("01","모델은 어떻게 만들어졌나 —","데이터, 구조, 알고리즘.","무엇을 맞히는 모델이고 어떤 데이터로 어떻게 학습했는지 설명합니다.",0);

// ---------- 4. 1.1 문제 정의와 구조 ----------
{ const s=pres.addSlide(); header(s,"1.1 문제 정의와 모델 구조","'과거 웨어러블 → 다음 검진값'을 맞히는 모델입니다 —","검진 이력이 있으면 개인화(M1), 없으면 웨어러블 전용(M0)으로 나눕니다.");
  card(s,0.75,2.15,3.75,2.55,"입력 (예측 시점 이전만)",C.navy,["· 웨어러블 16종: 걸음·심박·수면·SpO2·혈압·체성분 등 (관측창 7/30/90일 요약)","· 직전 검진값(개인 기준선)·경과일·추세","· 성별·연령","시간 누출 금지: 검진일 이후 데이터는 절대 입력에 넣지 않음"]);
  card(s,4.8,2.15,3.75,2.55,"출력 (검진 항목 10종)",C.navy,["· 혈압(수축기·이완기), 체중·BMI·허리둘레","· 공복혈당, 지질 4종(총콜·HDL·LDL·중성지방)","· 예측값 + 85% 구간 + 기준 초과 확률 + 변화 방향","· 근거 부족 시 '보류(ABSTAIN)'와 사유"]);
  card(s,8.85,2.15,3.8,2.55,"세 가지 값을 엄격히 구분",C.navy,["actual_*  최근 실제 검진값","measured_*  웨어러블 직접 측정 요약(예측 아님)","pred_*  검증 통과 모델의 예측값","검증 전에는 pred_*를 서비스하지 않음"]);
  // 파이프라인 흐름
  const steps=[["① 데이터 통합","자체+공공 한 테이블\n출처표시·가중치"],["② 알고리즘 파일럿","5개 후보 교차검증\n항목별 최적 선택"],["③ 학습·튜닝","통합모델 v1.3\n개인화 M1 v3"],["④ 봉인 검증","사용자 20% 봉인\n기준선 대비 승격"],["⑤ 서비스 산출","사용자당 1행\n394명 출력"]];
  steps.forEach((st,i)=>{ const x=0.75+i*2.42; s.addShape(pres.ShapeType.roundRect,{x,y:5.05,w:2.2,h:1.05,rectRadius:0.08,fill:{color:i===3?C.navy:C.bg2},line:{color:i===3?C.navy:C.line,width:1}});
    s.addText(st[0],{x:x+0.12,y:5.12,w:2,h:0.3,fontFace:F.s,fontSize:12,color:i===3?C.white:C.navy,isTextBox:true,margin:0});
    s.addText(st[1],{x:x+0.12,y:5.42,w:2,h:0.62,fontFace:F.m,fontSize:10,color:i===3?"DCE6FF":C.gray,valign:"top",isTextBox:true,margin:0});
    if(i<4) s.addText("›",{x:x+2.2,y:5.35,w:0.22,h:0.4,fontFace:F.x,fontSize:18,color:C.light,align:"center",isTextBox:true,margin:0}); });
  keyBox(s,"핵심: 봉인 검증(④)을 통과한 항목만 예측값으로 서비스하고, 통과하지 못한 항목은 '직전값 유지' 또는 '보류'로 정직하게 표시합니다.",6.28);
  source(s,"구축가이드 v1.3 5장·7장, m1.py / serve.py 구현.",6.78);
  footer(s); }

// ---------- 5. 1.2 데이터 ----------
{ const s=pres.addSlide(); header(s,"1.2 학습 데이터 — 공공 + 자체 통합 테이블","공공데이터로 양을 확보하고, 검증은 자체 데이터로만 합니다 —","병목은 '웨어러블 착용 후 받은 검진' 쌍이 15건뿐이라는 점입니다.");
  s.addText("통합 학습 테이블 구성 (행 수)",{x:0.75,y:2.1,w:6,h:0.3,fontFace:F.s,fontSize:13,color:C.dark,isTextBox:true,margin:0});
  s.addChart(pres.ChartType.bar,[{name:"행 수",labels:["NHANES (미국, 손목 가속도+검진)","자체 검진 (394명, 2017~2026)","KNHANES (한국, 걸음·강도+검진)"],values:[9981,1549,592]}],
    Object.assign({},chartBase,{x:0.75,y:2.4,w:6.3,h:2.6,barDir:"bar",catAxisOrientation:"maxMin",chartColors:[C.navy],showValue:true,dataLabelPosition:"outEnd",showLegend:false,valAxisHidden:true,valGridLine:{style:"none"},catAxisLabelFontSize:10.5}));
  s.addText("자체 자산: 웨어러블 16종(심박 1,060만 행/217명, 469명), 검진 1,865건/374명. 출처 표시 변수와 가중치(자체 > 한국 공공 3.0 > 미국 공공 1.0)로 단일 모델을 학습합니다.",{x:0.75,y:5.05,w:6.3,h:0.75,fontFace:F.m,fontSize:10.5,color:C.gray,valign:"top",isTextBox:true,margin:0,lineSpacingMultiple:1.15});
  s.addShape(pres.ShapeType.rect,{x:7.5,y:2.1,w:5.15,h:3.7,fill:{color:C.bg2},line:{color:C.line,width:1}});
  s.addText("왜 라벨이 병목인가",{x:7.75,y:2.28,w:4.7,h:0.35,fontFace:F.s,fontSize:14,color:C.dark,isTextBox:true,margin:0});
  stat(s,7.75,2.75,2.3,"15건",  "착용 후 검진 쌍 (12명)",C.red);
  stat(s,10.2,2.75,2.3,"30명",  "검증 개시 게이트 (정책)",C.navy);
  s.addText([{text:"우리 웨어러블 수집은 2025-12에 시작됐고 검진은 대부분 그 이전(2017~2025)입니다. 예측은 '검진 이전 웨어러블'만 쓸 수 있으므로, 2026년 이후 검진만 웨어러블→검진 검증에 쓸 수 있습니다.",options:{breakLine:true,paraSpaceAfter:6}},
              {text:"반면 '직전 검진값 → 다음 검진값' 개인화(M1)는 1,130행이 있어 지금 검증이 가능합니다. 이것이 현재 성능 검증의 중심입니다."}],
    {x:7.75,y:4.05,w:4.7,h:1.7,fontFace:F.m,fontSize:10.5,color:C.text,valign:"top",isTextBox:true,margin:0,lineSpacingMultiple:1.15});
  keyBox(s,"핵심: 공공데이터는 '학습에만' 들어가고 평가에는 한 행도 들어가지 않습니다 — 모든 성능 수치는 우리 사용자에게서 측정한 값입니다.",6.0);
  source(s,"unified_table.parquet(12,122행), DB 감사 2026-09-01, m0_forward_eval(2026-09-10).",6.6);
  footer(s); }

// ---------- 6. 1.3 알고리즘 ----------
{ const s=pres.addSlide(); header(s,"1.3 알고리즘 선택 — 파일럿 비교 후 데이터가 고르게 했습니다","5개 후보를 사용자 단위 교차검증으로 비교했습니다 —","표 형태 데이터에서는 그래디언트 부스팅이 가장 많이 이겼습니다.");
  s.addText("공공 활동→검진 파일럿: 항목별 1위 횟수 (10개 항목)",{x:0.75,y:2.1,w:6.3,h:0.3,fontFace:F.s,fontSize:13,color:C.dark,isTextBox:true,margin:0});
  s.addChart(pres.ChartType.bar,[{name:"1위 횟수",labels:["그래디언트 부스팅 (HistGBM)","랜덤 포레스트","MLP (딥러닝)","엘라스틱넷 (선형)"],values:[5,2,2,1]}],
    Object.assign({},chartBase,{x:0.75,y:2.4,w:6.3,h:2.7,barDir:"bar",catAxisOrientation:"maxMin",chartColors:[C.navy],showValue:true,dataLabelPosition:"outEnd",showLegend:false,valAxisHidden:true,valGridLine:{style:"none"}}));
  s.addText("10개 항목 모두 '평균으로 맞히기' 기준선을 이겼습니다. MLP(딥러닝)는 신호가 약한 지질 2개에서만 근소하게 앞섰습니다.",{x:0.75,y:5.15,w:6.3,h:0.6,fontFace:F.m,fontSize:10.5,color:C.gray,valign:"top",isTextBox:true,margin:0,lineSpacingMultiple:1.15});
  table(s,[["모델","역할","쓰이는 곳"],["HistGradientBoosting","주 알고리즘 (항목별 튜닝)","통합 모델 v1.3, 분류 후보"],["혼합효과 (경험적 베이즈 축소)","개인 이력↔모집단 평균 가중","M1: 이완기·혈당 등 7개 항목 최적"],["ElasticNet (선형)","안정적 소표본 회귀","M1: 수축기혈압 최적"],["로지스틱 / HistGBM 분류","기준 초과 여부 판별","임계값 플래그 4종"],["자기지도 인코더 (딥러닝)","웨어러블 리듬 표현 사전학습","라벨 축적 후 투입 예정"]],
    [1.85,1.55,1.75],7.5,2.1,{fontSize:9.5,rowH:0.5});
  keyBox(s,"핵심: 하이퍼파라미터 튜닝의 개선폭이 작았습니다 — 성능 병목은 기법이 아니라 라벨의 양이라는 뜻입니다.",6.0);
  source(s,"benchmark_report.json(Pilot A, GroupKFold 5), tune(랜덤서치 25회), m1_v3 후보 비교.",6.6);
  footer(s); }

// ---------- 7. 섹션 02 ----------
divider("02","성능은 어느 정도인가 —","봉인 테스트 결과와 그 의미.","우리 사용자 59명 봉인셋에서 1회만 평가한 수치입니다. 공공데이터 수치는 쓰지 않았습니다.",1);

// ---------- 8. 2.1 M1 성능 ----------
{ const s=pres.addSlide(); header(s,"2.1 개인화 예측(M1) — 직전 검진값보다 얼마나 정확한가","혈압·공복혈당은 '직전값 그대로'보다 14~20% 오차가 줄었습니다 —","체중·BMI는 직전값이 이미 정확해 모델을 쓰지 않는 것이 옳습니다.");
  s.addText("봉인셋 평균절대오차(MAE) — 낮을수록 정확",{x:0.75,y:2.1,w:6.5,h:0.3,fontFace:F.s,fontSize:13,color:C.dark,isTextBox:true,margin:0});
  s.addChart(pres.ChartType.bar,[{name:"직전값 그대로",labels:["수축기혈압 (mmHg)","이완기혈압 (mmHg)","공복혈당 (mg/dL)"],values:[10.83,8.07,15.17]},{name:"우리 모델",labels:["수축기혈압 (mmHg)","이완기혈압 (mmHg)","공복혈당 (mg/dL)"],values:[8.78,6.96,12.10]}],
    Object.assign({},chartBase,{x:0.75,y:2.4,w:6.5,h:3.1,barDir:"col",chartColors:[C.light,C.navy],showValue:true,dataLabelPosition:"outEnd",dataLabelFormatCode:"0.0",showLegend:true,legendPos:"b",barGapWidthPct:60,valAxisMinVal:0}));
  table(s,[["항목","서빙 경로","봉인 결과","R²"],["수축기혈압","모델","8.78 vs 10.83 (−19%)","0.31"],["이완기혈압","모델(혼합효과)","6.96 vs 8.07 (−14%)","0.24"],["공복혈당","모델(혼합효과)","12.10 vs 15.17 (−20%)","0.17"],["체중 · BMI","직전값 유지","직전값 R² 0.95 / 0.91","—"],["허리둘레","직전값 유지","직전값 MAE 3.9 cm","—"],["지질 4항목","교차특징 모델","이력 없어도 310명 예측","0.07~0.21"]],
    [1.3,1.4,1.7,0.7],7.55,2.1,{fontSize:9.5,rowH:0.44,hl:[]});
  s.addText("예측구간(85% 명목) 실제 포함률 0.80~0.93 — 구간이 '약속한 만큼' 실제값을 담습니다.",{x:7.55,y:5.25,w:5.1,h:0.5,fontFace:F.m,fontSize:10,color:C.gray,valign:"top",isTextBox:true,margin:0});
  keyBox(s,"핵심: 승격 규칙은 사전에 정하고 봉인셋을 보지 않았습니다 — 오차 3% 이상 개선·과반 폴드 승리·표본 정책(학습 100명·봉인 30명)을 모두 통과한 항목만 '모델'입니다.",6.0);
  source(s,"m1_v3 봉인 테스트(사용자 59명, 1회 평가). MAE=평균절대오차, R²=설명력(1에 가까울수록 좋음).",6.6);
  footer(s); }

// ---------- 9. 2.2 분류 ----------
{ const s=pres.addSlide(); header(s,"2.2 기준 초과 판별 — '다음 검진에서 기준을 넘는가'","정확한 수치보다 '기준 초과 여부'는 훨씬 잘 맞힙니다 —","비만·복부비만은 AUROC 0.96, 고혈압·혈당장애는 0.82입니다.");
  s.addText("봉인셋 AUROC — 0.5는 동전 던지기, 1.0은 완벽 (관례: 0.8+ 양호, 0.9+ 우수)",{x:0.75,y:2.1,w:7,h:0.3,fontFace:F.s,fontSize:12.5,color:C.dark,isTextBox:true,margin:0});
  s.addChart(pres.ChartType.bar,[{name:"직전 상태 유지 (기준선)",labels:["고혈압 ≥140/90","공복혈당 ≥100","비만 BMI≥25","복부비만"],values:[0.77,0.77,0.863,0.861]},{name:"우리 모델",labels:["고혈압 ≥140/90","공복혈당 ≥100","비만 BMI≥25","복부비만"],values:[0.82,0.819,0.962,0.955]}],
    Object.assign({},chartBase,{x:0.75,y:2.4,w:7.0,h:3.15,barDir:"col",chartColors:[C.light,C.navy],showValue:true,dataLabelPosition:"outEnd",dataLabelFormatCode:"0.00",showLegend:true,legendPos:"b",barGapWidthPct:60,valAxisMinVal:0.5,valAxisMaxVal:1.0,valAxisMajorUnit:0.1}));
  card(s,8.1,2.1,4.55,3.45,"읽는 법과 서비스 적용",C.navy,["· 판별 모델은 '다음 검진에서 기준을 넘을 확률'을 내고, 0.5 이상이면 플래그를 켭니다.","· 네 문제 모두 봉인셋에서 '직전 상태 유지' 기준선보다 높았고, 이 4종만 서비스 플래그로 씁니다.","· 변화 방향(악화/유지/개선)은 수축기혈압(정확도 0.48, 다수기준 0.30)·공복혈당(0.575 vs 0.425)에서만 유효해 두 항목만 제공합니다.","· 고중성지방(≥150)은 양성 8건뿐이라 정책상 보류입니다."]);
  keyBox(s,"핵심: 서비스가 실제로 묻는 질문('나빠졌나, 기준을 넘었나')에는 회귀 R²보다 훨씬 높은 판별력으로 답할 수 있습니다.",6.0);
  source(s,"clinical_report.json 봉인셋(사용자 59명). AUROC=수신자조작특성 곡선 아래 면적.",6.6);
  footer(s); }

// ---------- 10. 2.3 유의성과 한계 ----------
{ const s=pres.addSlide(); header(s,"2.3 이 수치는 객관적으로 유의미한가","혈압·혈당 개선은 통계적으로 유의합니다 —","단, 봉인셋 59명이라 구간이 넓고 웨어러블 단독 혈압은 유의하지 않습니다.");
  table(s,[["평가 대상","지표","결과 (95% 신뢰구간)","판정"],
    ["수축기혈압 M1","오차 감소 (모델−직전값)","−2.05 mmHg  [−2.94, −1.24]","유의 — 구간 전체가 개선"],
    ["이완기혈압 M1","오차 감소","−1.10 mmHg  [−1.76, −0.45]","유의"],
    ["공복혈당 M1","오차 감소","−3.07 mg/dL  [−4.79, −1.61]","유의"],
    ["비만 판별","AUROC 개선 (vs 직전 상태)","+0.099  [+0.043, +0.163]","유의"],
    ["복부비만 판별","AUROC 개선","+0.094  [+0.045, +0.164]","유의"],
    ["고혈압 판별","AUROC 개선","+0.050  [−0.037, +0.122]","판별력 양호(0.82)이나 개선은 미확정 — 표본 확대 필요"],
    ["공복혈당 판별","AUROC 개선","+0.049  [−0.004, +0.096]","경계 — 표본 확대 필요"],
    ["웨어러블→혈압 (M0 대리학습)","설명력 R²","≈ 0 (0.05)","유의하지 않음 — 현 신호로 불가"]],
    [2.4,2.2,3.2,4.1],0.75,2.1,{fontSize:10,rowH:0.4,hl:[6,7,8]});
  keyBox(s,"핵심: '유의'는 사용자 단위 부트스트랩 2,000회의 95% 구간이 0을 포함하지 않는다는 뜻입니다. 노란 행은 결론을 내리기에 표본이 더 필요한 항목입니다.",6.0);
  source(s,"significance.json — 봉인셋 사용자 59명, 사용자 클러스터 부트스트랩(B=2,000). 정책 최소 30명은 충족.",6.6);
  footer(s); }

// ---------- 11. 섹션 03 ----------
divider("03","무엇을 보완해야 하나 —","한계와 다음 단계.","성능을 올리는 지렛대는 모델 기법이 아니라 라벨입니다.",2);

// ---------- 12. 3.1 보완 과제 ----------
{ const s=pres.addSlide(); header(s,"3.1 한계와 보완 과제","세 가지 한계가 확인됐고, 각각 해결 경로가 정해져 있습니다 —","가장 큰 지렛대는 '검진 결과 업로드'입니다.");
  card(s,0.75,2.1,3.85,2.95,"① 라벨 부족 — M0 보류",C.red,["착용 후 검진 쌍 15건(12명) < 게이트 30명","→ 웨어러블 사용자 중 연례 검진자 180명 대상 검진 결과 업로드 캠페인","→ 자동 평가 장치가 유입을 추적, 30명 도달 시 검증 재개","→ 분기 재학습으로 자체 데이터 비중 확대"]);
  card(s,4.75,2.1,3.85,2.95,"② 웨어러블 단독 혈압 — 불가",C.orange,["심박·수면·걸음(야간·변동성 포함)으로 혈압 설명력 ≈0","→ 혈압은 '직전 검진 + 기기 측정값' 기반으로 서비스","→ PPG 파형 등 새 신호 확보 전에는 약속하지 않음","→ 체중은 웨어러블만으로 R² 0.41 추정 가능"]);
  card(s,8.75,2.1,3.9,2.95,"③ 지질·고TG — 라벨 희소",C.navy,["반복 지질 검진 사용자 62명, 고TG 양성 8건","→ 교차특징 모델로 310명까지 예측 범위 확장(R² 0.07~0.21)","→ 지질 재검 라벨 축적 후 개인화·판별 재시도","→ 자기 이력이 있으면 직전값 우선(하이브리드)"]);
  table(s,[["다음 단계","내용","효과"],["1. 검진 업로드 캠페인","연례 검진자 180명, 업로드 리드타임 단축","모든 트랙의 상한을 올리는 유일한 지렛대"],["2. 의료진 검토 화면","예측값·구간·플래그·방향을 검토용으로 제공","검증 전 사용자 노출 없이 임상 피드백 확보"],["3. 분기 재학습·계보 기록","자체 비중 확대, 버전별 구성비 기록","'검증·완성은 자체 데이터'로 입증"]],
    [2.3,5.2,4.4],0.75,5.2,{fontSize:10,rowH:0.36});
  source(s,"구축가이드 v1.3 7~8장, m0_forward_eval.jsonl, proxy_report.json.",6.75);
  footer(s); }

pres.writeFile({fileName:"/Users/jaeho.oh/Downloads/SiBC_건강검진예측모델_구축검증결과_발표자료_20260911.pptx"}).then(f=>console.log("written",f));
