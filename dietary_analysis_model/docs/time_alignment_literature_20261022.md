# 섭취–소모 시간 정렬 문헌 정리 (2026-10-22)

목적: [system_design_20261022.md](system_design_20261022.md) §3.6의 세 결정(정렬 단위, 하루 경계, 운동 후 창)에 답한다.
질문은 네 가지다. (1) 혼합 식사의 소화·흡수 완료 시간, (2) 식후 저장과 공복기 동원의 시간 경과,
(3) 에너지 균형 연구의 하루 정렬 관행과 하루 경계 정의, (4) 운동 후 영양 이용이 높아지는 시간창.

조사 방법: PubMed 검색(2026-10-22)과 웹 검색. 아래 문헌 정보는 PubMed에서 가져왔고, 각 문헌의 DOI를 §7에 링크했다.
초록 수준에서 확인한 내용이며 원문을 전부 읽은 것은 아니다. 원문 확인이 필요한 항목은 §6에 적었다.
보고서 형식(docx)은 `SiBC_식이분석_섭취활동_시간정렬_문헌조사보고서_20261022.docx`에 있다.

---

## 0. 결론 요약

| 결정 항목 | 결론 | 근거 강도 | 핵심 근거 |
|---|---|---|---|
| 정렬 단위 | **같은 날 24시간.** 섭취일과 소모일을 하루 뒤로 밀어 맞추지 않는다 | 강함 | 혼합 식사 흡수는 4~6시간 내 완료(§1). 식후 저장분은 그날 밤~다음 날 아침에 동원(§2). 에너지 균형 연구는 같은 날 단위로 짝짓고, 하루 단위 상관은 원래 없으며 주 단위 이상에서 나타남(§3) |
| 하루 경계 | **자정(00시) 기본.** 야식은 경계를 옮기지 않고 **별도 플래그**로 표기한다. 새벽 경계로의 이동은 웨어러블 하루 경계를 함께 옮길 수 있을 때만 검토 | 중간 | 식이조사 관행과 웨어러블 일일 집계가 모두 자정 기준(§3.4). 늦은 식사의 문제는 "어느 날에 속하는가"가 아니라 "늦게 먹었다는 사실 자체"가 대사에 불리하다는 점(§3.5) |
| 운동 후 창 | **운동 종료 후 2시간**을 끼니 레코드의 플래그로 둔다. 열량 균형 판정은 완화하지 않고(당일 합산), 단백질·탄수화물의 "적절" 범위 해석에만 쓴다 | 중간 | 단백질은 운동 직후~2시간, 급속 글리코겐 회복은 4시간 내가 핵심(§4). 좁은 창의 중요성은 과장되었다는 반론도 있음(§4.2). 운동 후 당일 섭취 보상은 일어나지 않음(§3.3) |

부수 결론:

- 하루 단위 에너지 지수(섭취 − 소모)는 생리학적으로도 통계적으로도 노이즈가 크다. **7일 이상 창의 평균과 추세**로만 쓴다는 설계 원칙(§5.1)이 문헌으로 뒷받침된다.
- 개인 baseline에 필요한 일수는 영양소별로 크게 다르다(§3.6). 에너지·다량영양소는 수 일~1주, 변동이 큰 영양소는 수 주. 6-b 학습 품질 평가의 출발점으로 쓴다.
- 과소보고 탐지에는 섭취 열량/기초대사량 비율 컷오프(Goldberg 1991이 제안한 영양역학 표준 방법)를 쓸 수 있으며, 활동 수준을 반영해야 한다(§3.7).

---

## 1. 질문 1 — 혼합 식사의 소화·흡수 완료 시간

### 1.1 위 배출

| 식사 | 위 배출 반감기 | 잔류 | 출처 |
|---|---|---|---|
| 아시아식 쌀밥 + 계란 267 kcal, 건강인 189명 | 중앙값 68.7분(5~95백분위 45~108분) | 2시간 16.3%, 4시간 1.1% | Vasavid 2014 [1] |
| 노팅엄 시험식(액체 400 mL + 고형 성분) | 액체 44분, 고형 162분(참조구간 144~193분) | — | Parker 2017 [2] |
| 계란 샌드위치 표준식 | 90분 측정에서 50% 전후 배출 | — | Ziessman 2004 [3] |

쌀밥 기반 식사의 위 배출 자료[1]는 한국 식사에 가장 가깝다. 고형 식사는 2시간에 대부분, 4시간에 거의 전부 위를 떠난다.

### 1.2 탄수화물

Taylor 1996[4]은 액체 혼합 식사 후 간 글리코겐 농도를 13C 핵자기공명으로 추적했다. 간 포도당 생산은 식후 30분 내에 완전히 억제되었고, 간 글리코겐은 식후 **318분(약 5.3시간)에 정점**을 찍은 뒤 감소했다. 간 포도당 생산은 255분부터 기저 수준으로 빠르게 돌아왔다. 즉 식사 탄수화물의 흡수와 저장은 식후 4~5시간 안에 끝난다.

### 1.3 지방

식사 지방은 킬로미크론으로 수 시간에 걸쳐 순환하며, 식후 비에스테르화 지방산 농도를 올리고 간으로 8~12%(정상인), 10~16%(당뇨·지방간)가 유입된다(Lambert & Parks 2012 [5]). 지방의 흡수·처리는 탄수화물보다 느려 식후 6~8시간까지 이어진다.

### 1.4 결론

혼합 식사의 소화·흡수는 **4~6시간, 늦어도 8시간 안에 완료**된다. "오늘 저녁 섭취가 내일 저녁부터 에너지로 쓰인다"는 모델은 성립하지 않는다.

---

## 2. 질문 2 — 식후 저장과 공복기 동원의 시간 경과

### 2.1 간 글리코겐

- 식후 간 글리코겐 순합성은 28 g(식사 탄수화물의 약 19%)이었고, 5시간 정점 후 0.26 mmol/L/min 속도로 **바로 감소**했다[4]. 저장과 동원 사이에 "대기 시간"이 없다.
- 68시간 공복 추적에서 당신생은 **첫 22시간 동안 이미 포도당 생산의 64%**를 차지했고, 이후 82%, 96%로 올라갔다(Rothman 1991 [6]). 간 글리코겐은 하룻밤~하루 안에 대부분 소진된다.
- 정상인의 식후 4시간 간 글리코겐 농도는 282 mmol/L, 야간 공복 중 순 글리코겐 분해 속도는 2.8 µmol/kg/min이었다(Magnusson 1992 [7]).
- 잘 훈련된 자전거 선수에게 체중 kg당 3 g의 탄수화물 아침을 먹인 뒤 3시간 동안 간 글리코겐 **총량**은 변하지 않았다. 농도는 올랐지만 간 용적이 줄었기 때문이다(Fuchs 2025 [8]). 글리코겐 농도만으로 저장량을 해석하면 과대평가할 수 있다.

### 2.2 탄수화물·지방 균형의 조절 시간 척도

Flatt 1995[9][10]에 따르면 글리코겐 저장량이 작기 때문에 **탄수화물 산화는 섭취에 빠르게(하루 안에) 맞춰지고**, 지방 산화는 지방 섭취가 아니라 탄수화물 경제에 좌우된다. 지방 균형의 누적 오차는 **수 주~수 개월에 걸쳐 체지방량 변화**로 조정된다. 즉 식사 지방은 저장되면 기존 저장분과 섞여 어느 끼니의 것인지 추적할 수 없다.

### 2.3 결론

섭취 에너지가 "쌓이고 나서 쓰이는" 지연은 **수 시간에서 하룻밤**이다. 저녁 식사의 탄수화물은 그날 밤과 다음 날 아침 공복기에 쓰이고, 지방은 저장 풀에 섞인다. 하루 뒤로 미는 정렬에는 생리학적 근거가 없다.

---

## 3. 질문 3 — 에너지 균형 연구의 하루 정렬 관행과 하루 경계

### 3.1 같은 날 섭취–소모 상관은 원래 없다

Edholm 1970[11]은 군 신병 64명의 섭취와 35명의 소모를 3주간 매일 측정했다. **같은 날 섭취와 소모 사이에 유의한 관계가 없었고** 자기상관·교차상관도 매우 작았다. 그러나 **3주 전체 기간**에서는 유의한 상관이 나타났다(일부 센터 r = 0.788). 1955년 선행 연구(Edholm, Fletcher, Widdowson, McCance)도 같은 계열이다. 이 결과는 섭취와 소모를 어느 날에 맞추든 하루 단위 균형은 노이즈라는 뜻이며, 하루 뒤로 밀어 정렬해야 할 이유를 제공하지 않는다.

### 3.2 체중 반응의 시간 척도

- 에너지 섭취 변화에 대한 체중 반응은 느리며 **반감기가 약 1년**이다. 미국 성인 비만 유행은 하루 약 30 kJ(7 kcal)의 지속적 불균형으로 설명된다(Hall 2011 [12]).
- 2년 열량 제한 연구(CALERIE) 자료로 두 예측 모델을 검증한 결과, 평균 수준에서는 잘 맞았지만 **개인 수준 예측은 변동이 커서 신중한 해석**이 필요했다. 섭취 변화의 측정 불확실성이 개인 변동의 주요 원인이었다(Guo, Brager, Hall 2018 [13]). 이 연구에서 쓰인 "섭취–균형 방법"(체성분 변화와 소모량으로 섭취를 역산)은 날짜가 아니라 **수 주~수 개월 구간**으로 균형을 계산한다.
- 체중 조절은 섭취·소모가 동적으로 맞물려 저항하는 체계이며, 단순히 "덜 먹고 더 움직이면 된다"는 정적 해석은 맞지 않는다(Hall & Guo 2017 [14]).

### 3.3 운동 당일 섭취 보상은 없다

51개 시험의 메타분석에서 급성 운동은 **절대 섭취량에 거의 영향이 없었고**(효과크기 0.14), 상대 섭취량(섭취 − 운동 소모)은 큰 음의 효과(−1.35)를 보였다. 사람들은 운동 직후 수 시간 안에 운동으로 쓴 에너지를 먹어서 보상하지 않는다(Schubert 2013 [15]). 따라서 운동 소모 열량을 **당일 섭취 기준량에 반영**하는 것은 타당하며, 운동 후 끼니를 "보상 섭취"로 미리 가정할 필요는 없다.

### 3.4 하루 경계 관행

| 영역 | 경계 | 확인 상태 |
|---|---|---|
| 식이 조사(24시간 회상법) | 조사 전날 하루(자정~자정)가 관행. 국민건강영양조사도 24시간 회상법을 쓴다 | 질병관리청 조사지침 원문은 이번 검색에서 확인하지 못함 |
| 소비자 웨어러블(Fitbit, Garmin) | 사용자 커뮤니티 보고상 **로컬 자정에 일일 열량이 0으로 리셋**. 자정을 넘는 운동은 날짜별로 나뉘어 집계되거나 중복 집계 사례가 보고됨 | 공식 문서 미확인. 우리 서비스 기기의 하루 경계는 2단계에서 직접 확인 |
| 에너지 균형 연구 | 24시간 호흡실·이중표지수는 **하루 또는 수 일~수 주 구간** 단위. 경계 이동 관행 없음 | — |

### 3.5 늦은 식사의 문제는 날짜 귀속이 아니라 시간 자체

최근 종설들은 늦은 시간대 섭취가 **총 섭취량과 식사 구성이 같아도** 식후 혈당 조절, 인슐린 감수성, 지질 처리에 불리하며 체중 증가와 연관된다고 정리한다(Alotaibi 2026 [16]; Alum 2025 [17]; Reytor-González 2025 [18]; Davis 2022 [19]; Beccuti 2017 [20]). 저녁형 시간유형은 섭취가 밤으로 몰리고 과체중·대사 지표가 나쁜 경향이 있다(van der Merwe 2022 [21]). 같은 식사라도 아침보다 저녁에 먹으면 식사 유발 열생성이 낮고 혈당·인슐린 상승이 크다(Richter 2020 [22], 초록·보도자료 확인). 따라서 야식은 어느 날로 넘길지의 문제가 아니라 **"늦게 먹었다"는 사실을 지표로 남기는 것**이 맞다.

### 3.6 개인 baseline에 필요한 일수

- 영국 남성 332명의 1주 이상 식사 기록 분석에서, 개인을 섭취 분포의 상·하위 1/3로 80% 신뢰도로 분류하는 데 필요한 일수는 **당·총탄수화물 2~3일**부터 **콜레스테롤·지방산 비율 2~3주**까지 영양소별로 달랐다. 하루 기록으로는 어떤 영양소도 80% 신뢰도에 못 미쳤고, 1주 기록은 대부분 영양소에서 충족했다(Marr & Heady 1986 [23]).
- 영아부터 노인까지 6개 연구에서 에너지와 28개 영양소의 필요 기록 일수를 추정한 결과, **7일 기록도 흔히 가정하는 정확도로 개인을 서열화하지 못했다**. 철·아연 등은 여러 짧은 기간으로 나눠 기록해야 하고, 일부 영양소는 식사 기록보다 빈도 설문이 적합했다(Nelson 1989 [24]).
- 핵심 변수는 영양소별 **개인 간 분산 / 개인 내 분산 비율**이다. 우리 데이터로 이 비율을 실측하면 영양소별 "개인 baseline 사용 가능 최소 유효 일수"가 나온다. 설계 문서 §5.2의 A형 학습 평가가 이것이다.

### 3.7 과소보고 탐지

과소보고 탐지의 표준 방법은 "기록된 섭취 열량 ÷ 기초대사량" 비율 검사다. 사람은 기초대사량보다 적게 먹고 체중을 유지할 수 없으므로 비율이 하한 아래면 생리적으로 불가능한 기록, 즉 과소보고로 본다. Goldberg 1991은 이 비율의 하한을 **1.35(기초대사량 실측 시)**로 제시했고, 발표된 조사 68개 집단 중 46개(68%)가 컷오프 아래였다. Black 2000은 이중표지수와 비교해 단일 활동계수(1.55)를 쓰면 민감도 약 0.5, 특이도 약 1.0이며, **집단 또는 개인의 실제 활동 수준을 반영**해야 한다고 결론했다(웹 검색으로 초록 확인 [25]). 웨어러블 소모량이 있으면 개인 활동 수준을 반영한 컷오프를 만들 수 있다.

### 3.8 결론

같은 날 24시간 단위, 자정 경계가 관행이고 생리학과도 맞는다. 하루 단위 균형은 노이즈이므로 지수는 주 단위 이상 창에서만 해석한다. 야식은 경계 이동 대신 플래그로 처리한다.

---

## 4. 질문 4 — 운동 후 영양 이용이 높아지는 시간창

### 4.1 공식 입장

국제스포츠영양학회 입장문(Kerksick 2017 [26])은 다음을 제시한다.

- 회복 시간이 **4시간 미만**이면 글리코겐 급속 회복을 위해 시간당 체중 kg당 탄수화물 1.2 g(또는 탄수화물 0.8 g + 단백질 0.2~0.4 g).
- 고품질 단백질을 **운동 직후~2시간** 안에 섭취하면 근단백 합성이 크게 증가.
- 단백질은 하루 총량을 채우되 **약 3시간 간격**으로 나누는 것이 1차 강조점.
- 2008년 입장문(Kerksick 2008 [27])은 운동 후 30분 내 탄수화물, 직후~3시간 아미노산을 권고했다.

### 4.2 "좁은 창"에 대한 반론

Aragon & Schoenfeld 2013[28]은 운동 후 좁은 "동화 창"의 중요성, 나아가 존재 자체가 여러 요인에 따라 달라지며, 최근 증거가 고전적 견해에 도전한다고 정리했다. 운동 전 식사가 있었다면 창은 넓어진다. 즉 2시간 창은 **최대 효과를 노리는 선수용 권고**이고, 일반 사용자에게는 운동 전후 수 시간 안에 단백질을 포함한 식사를 하는 정도가 실용적 결론이다.

### 4.3 글리코겐 완전 회복과 운동 후 산소 소비

- 근 글리코겐의 완전한 회복에는 충분한 탄수화물과 **약 24시간**이 필요하다(Murray & Rosenbloom 2018 [29]).
- 운동 후 산소 소비 증가(EPOC)는 빠른 성분과 느린 성분으로 나뉘고, **고강도·장시간 운동 후에만 수 시간 지속**하며 저강도·단시간에서는 미미하다(Børsheim & Bahr 2003 [30]). 웨어러블이 운동 세션 열량만 기록하면 EPOC는 빠질 수 있으나 양이 작다.
- 급성 운동은 평균적으로 위 배출을 바꾸지 않았다. 저강도는 빠르게, 고강도는 느리게 하는 용량 반응이 있었다(Horner 2015 [31]).

### 4.4 결론

운동 종료 후 **2시간** 창을 끼니 레코드의 플래그로 둔다. 이 창에서 열량 균형 판정을 완화할 근거는 없다(열량은 당일 합산이고 보상 섭취도 없다). 다만 단백질·탄수화물 "적절" 범위를 해석할 때 참고 정보로 쓸 수 있고, 세부 규칙은 설계 문서 8.2의 6단계(웨어러블 결합)에서 정한다.

---

## 5. 설계 반영안 (§3.6 갱신)

| 결정 항목 | 채택값 | 근거 | 남은 확인 |
|---|---|---|---|
| 정렬 단위 | 같은 날 24시간 | §1, §2, §3.1~3.3 | 없음 |
| 하루 경계 | 자정 00시(로컬). 야식 플래그: 21시 이후 또는 취침 전 N시간 내 섭취(N은 수면 데이터 유무에 따라 결정) | §3.4, §3.5 | 우리 웨어러블의 일일 집계 경계와 자정 넘는 세션 처리 방식. 질병관리청 식품섭취조사 지침 원문 |
| 운동 후 창 | 운동 종료 후 2시간 플래그. 열량 판정 비완화, 단백질·탄수 해석 보조 | §4 | 웨어러블 운동 세션 시각 입수 가능 여부 |
| 에너지 지수 해석 단위 | 7일 이상 창의 평균과 창 간 비교 | §3.1, §3.2 | 설계 §5.1 평가로 확정 |
| 개인 baseline 최소 유효 일수 | 영양소별로 개인 내/간 분산 비율에서 산정. 초기 가설: 에너지·다량영양소 7일, 미량영양소 그 이상 | §3.6 | 설계 §5.2 A형 평가(5단계)에서 실측 |
| 과소보고 탐지 | 섭취/기초대사량 비율 컷오프, 개인 활동 수준 반영 | §3.7 | 웨어러블 결합 후 적용 |

---

## 6. 한계와 후속

- 위 배출 자료 중 쌀밥 기반 식사[1]는 태국 건강인 자료다. 한국인 자료가 있으면 교체한다.
- Richter 2020[22]과 Goldberg/Black[25]은 초록과 2차 자료로 확인했다. 수치를 설계 기준으로 쓰기 전에 원문을 확인한다.
- 질병관리청 식품섭취조사의 하루 정의와 소비자 웨어러블의 하루 경계는 공식 문서로 확인하지 못했다. 2단계(결정과 요청)에서 우리 서비스 기기 기준으로 직접 확인한다.
- 수면 시각을 하루 경계로 쓰는 대안(기상 기준일)은 웨어러블 수면 데이터가 결합된 뒤 재검토한다. 현재 결론은 자정 경계 + 야식 플래그다.
- 이 문서는 시간 정렬 규칙의 근거만 다룬다. 판정 구간 자체의 문헌은 [judgement_bands.md](judgement_bands.md), 가이드라인 목록은 [guidelines.md](guidelines.md)에 있다.

---

## 7. 참고문헌

PubMed에서 확인한 문헌이다. DOI가 없는 항목은 PubMed ID를 적었다.

1. Vasavid P et al. Normal solid gastric emptying values measured by scintigraphy using Asian-style meal: a multicenter study in healthy volunteers. J Neurogastroenterol Motil 2014;20(3):371-8. [DOI](https://doi.org/10.5056/jnm13114)
2. Parker HL et al. Clinical assessment of gastric emptying and sensory function utilizing gamma scintigraphy: establishment of reference intervals for the liquid and solid components of the Nottingham test meal in healthy subjects. Neurogastroenterol Motil 2017;29(11). [DOI](https://doi.org/10.1111/nmo.13122)
3. Ziessman HA et al. Standardization and quantification of radionuclide solid gastric-emptying studies. J Nucl Med 2004;45(5):760-4. PMID 15136623
4. Taylor R et al. Direct assessment of liver glycogen storage by 13C nuclear magnetic resonance spectroscopy and regulation of glucose homeostasis after a mixed meal in normal subjects. J Clin Invest 1996;97(1):126-32. [DOI](https://doi.org/10.1172/JCI118379)
5. Lambert JE, Parks EJ. Postprandial metabolism of meal triglyceride in humans. Biochim Biophys Acta 2012;1821(5):721-6. [DOI](https://doi.org/10.1016/j.bbalip.2012.01.006)
6. Rothman DL et al. Quantitation of hepatic glycogenolysis and gluconeogenesis in fasting humans with 13C NMR. Science 1991;254(5031):573-6. [DOI](https://doi.org/10.1126/science.1948033)
7. Magnusson I et al. Increased rate of gluconeogenesis in type II diabetes mellitus. A 13C nuclear magnetic resonance study. J Clin Invest 1992;90(4):1323-7. [DOI](https://doi.org/10.1172/JCI115997)
8. Fuchs CJ et al. Breakfast consumption does not rapidly increase liver or muscle glycogen content in well-trained cyclists. Am J Physiol Endocrinol Metab 2025;329(5):E774-E780. [DOI](https://doi.org/10.1152/ajpendo.00400.2025)
9. Flatt JP. Use and storage of carbohydrate and fat. Am J Clin Nutr 1995;61(4 Suppl):952S-959S. [DOI](https://doi.org/10.1093/ajcn/61.4.952S)
10. Flatt JP. Body composition, respiratory quotient, and weight maintenance. Am J Clin Nutr 1995;62(5 Suppl):1107S-1117S. [DOI](https://doi.org/10.1093/ajcn/62.5.1107S)
11. Edholm OG et al. Food intake and energy expenditure of army recruits. Br J Nutr 1970;24(4):1091-107. [Cambridge Core](https://www.cambridge.org/core/journals/british-journal-of-nutrition/article/food-intake-and-energy-expenditure-of-army-recruits/C5CC901A75A7BA15612810ED5638D17E) (웹 확인)
12. Hall KD et al. Quantification of the effect of energy imbalance on bodyweight. Lancet 2011;378(9793):826-37. [DOI](https://doi.org/10.1016/S0140-6736(11)60812-X)
13. Guo J, Brager DC, Hall KD. Simulating long-term human weight-loss dynamics in response to calorie restriction. Am J Clin Nutr 2018;107(4):558-565. [DOI](https://doi.org/10.1093/ajcn/nqx080)
14. Hall KD, Guo J. Obesity energetics: body weight regulation and the effects of diet composition. Gastroenterology 2017;152(7):1718-1727.e3. [DOI](https://doi.org/10.1053/j.gastro.2017.01.052)
15. Schubert MM et al. Acute exercise and subsequent energy intake. A meta-analysis. Appetite 2013;63:92-104. [DOI](https://doi.org/10.1016/j.appet.2012.12.010)
16. Alotaibi W. Chrononutrition and cardiometabolic health: circadian timing as a dimension of precision nutrition. Front Nutr 2026;13:1779033. [DOI](https://doi.org/10.3389/fnut.2026.1779033)
17. Alum EU. Circadian nutrition and obesity: timing as a nutritional strategy. J Health Popul Nutr 2025;44(1):367. [DOI](https://doi.org/10.1186/s41043-025-01102-y)
18. Reytor-González C et al. Chrononutrition and energy balance: how meal timing and circadian rhythms shape weight regulation and metabolic health. Nutrients 2025;17(13):2135. [DOI](https://doi.org/10.3390/nu17132135)
19. Davis R et al. The impact of meal timing on risk of weight gain and development of obesity: a review of the current evidence and opportunities for dietary intervention. Curr Diab Rep 2022;22(4):147-155. [DOI](https://doi.org/10.1007/s11892-022-01457-0)
20. Beccuti G et al. Timing of food intake: sounding the alarm about metabolic impairments? A systematic review. Pharmacol Res 2017;125(Pt B):132-141. [DOI](https://doi.org/10.1016/j.phrs.2017.09.005)
21. van der Merwe C, Münch M, Kruger R. Chronotype differences in body composition, dietary intake and eating behavior outcomes: a scoping systematic review. Adv Nutr 2022;13(6):2357-2405. [DOI](https://doi.org/10.1093/advances/nmac093)
22. Richter J et al. Twice as high diet-induced thermogenesis after breakfast vs dinner on high-calorie as well as low-calorie meals. J Clin Endocrinol Metab 2020;105(3):e211-e221. [DOI](https://doi.org/10.1210/clinem/dgz311) (초록·보도자료 확인, 원문 미열람)
23. Marr JW, Heady JA. Within- and between-person variation in dietary surveys: number of days needed to classify individuals. Hum Nutr Appl Nutr 1986;40(5):347-64. PMID 3781882
24. Nelson M, Black AE, Morris JA, Cole TJ. Between- and within-subject variation in nutrient intake from infancy to old age: estimating the number of days required to rank dietary intakes with desired precision. Am J Clin Nutr 1989;50(1):155-67. [DOI](https://doi.org/10.1093/ajcn/50.1.155)
25. Goldberg GR et al. Critical evaluation of energy intake data using fundamental principles of energy physiology: 1. Derivation of cut-off limits to identify under-recording. Eur J Clin Nutr 1991;45(12):569-81; Black AE. Critical evaluation of energy intake using the Goldberg cut-off for energy intake:basal metabolic rate. A practical guide to its calculation, use and limitations. Int J Obes 2000;24(9):1119-30. [Springer](https://link.springer.com/article/10.1038/sj.ijo.0801376) (웹 확인)
26. Kerksick CM et al. International Society of Sports Nutrition position stand: nutrient timing. J Int Soc Sports Nutr 2017;14:33. [DOI](https://doi.org/10.1186/s12970-017-0189-4)
27. Kerksick C et al. International Society of Sports Nutrition position stand: nutrient timing. J Int Soc Sports Nutr 2008;5:17. [DOI](https://doi.org/10.1186/1550-2783-5-17)
28. Aragon AA, Schoenfeld BJ. Nutrient timing revisited: is there a post-exercise anabolic window? J Int Soc Sports Nutr 2013;10(1):5. [DOI](https://doi.org/10.1186/1550-2783-10-5)
29. Murray B, Rosenbloom C. Fundamentals of glycogen metabolism for coaches and athletes. Nutr Rev 2018;76(4):243-259. [DOI](https://doi.org/10.1093/nutrit/nuy001)
30. Børsheim E, Bahr R. Effect of exercise intensity, duration and mode on post-exercise oxygen consumption. Sports Med 2003;33(14):1037-60. [DOI](https://doi.org/10.2165/00007256-200333140-00002)
31. Horner KM et al. Acute exercise and gastric emptying: a meta-analysis and implications for appetite control. Sports Med 2015;45(5):659-78. [DOI](https://doi.org/10.1007/s40279-014-0285-4)

보조 자료(웨어러블 하루 경계, 사용자 커뮤니티): [Fitbit Community — Data doesn't reset at midnight](https://community.fitbit.com/t5/Surge/Data-doesn-t-reset-at-midnight/td-p/1118129), [Garmin Forums — I need to reset my steps for the day](https://forums.garmin.com/apps-software/mobile-apps-web/f/garmin-connect-mobile-andriod/244059/i-need-to-reset-my-steps-for-the-day/1156389), [Garmin Forums — Garmin Connect repeats calories if not synced every day](https://forums.garmin.com/apps-software/mobile-apps-web/f/garmin-connect-mobile-ios/378031/garmin-connect-repeats-calories-if-not-synced-every-day/1803274). 공식 문서가 아니므로 참고용이다.
