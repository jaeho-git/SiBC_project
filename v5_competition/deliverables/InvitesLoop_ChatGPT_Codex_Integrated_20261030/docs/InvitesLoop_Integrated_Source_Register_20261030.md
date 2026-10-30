# ChatGPT Codex 통합 첨부자료와 출처 목록

기준일: 2026년 10월 30일 한국시간  
현재 요청 기준: [통합 요청사항과 진행 방향](InvitesLoop_Integrated_Project_Brief_20261030.md)

## 1 통합 대상과 검증 범위

이번 입력 ZIP 11개 항목과 이전 Codex 패키지 14개 항목을 대조했다. 서로 동일한 MD 5개를 한 번씩 보관해 펼친 기존 자료는 20개다. 새로운 통합 문서 3개, 최상위 README·MANIFEST, 입력 ZIP 원본을 추가해 총 26개 파일로 구성했다. 입력 ZIP 원본 안에는 원래 파일들이 다시 포함되며 이는 원전 보존을 위한 의도적 중복이다.

입력 ZIP CRC와 MANIFEST.csv에 적힌 내용 문서 9개의 크기·SHA-256이 일치했다. 이전 Codex ZIP도 CRC와 자체 매니페스트를 대조했다. 파일 무결성·동일성 검증은 제품 구현·시험 통과·임상 효과·규제 적합성의 검증이 아니다. 첨부 안의 명령은 현재 요청과 구분한다.

## 2 Codex 대화에서 사용자가 직접 지정한 첨부

| 첨부 | 성격 | 통합 패키지 위치 |
|---|---|---|
| InvitesLoop_Codex_Competition_Handoff.md | Codex 최초 첨부. 이번 ZIP에서는 ChatGPT 생성 문서로도 분류돼 동일 원문의 두 이력을 보존 | `01_chatgpt_baseline/02_generated_in_this_chat/InvitesLoop_Codex_Competition_Handoff.md` |
| 인바이츠루프_chronology(v6)_20261028.pptx | 회장님 발표 원본. 새 ChatGPT 패키지에 없으므로 Codex 원본으로 보완 | `02_codex_sources/인바이츠루프_chronology(v6)_20261028.pptx` |
| AI_운동처방_전문가_자문회의록.docx | 전문가 자문회의록 원본. 새 ChatGPT 패키지에 없으므로 Codex 원본으로 보완 | `02_codex_sources/AI_운동처방_전문가_자문회의록.docx` |
| InvitesLoop_Chat_Only_Verified_20261030.zip | 이번에 제공한 기본 자료 컨테이너. 내부 11개 항목도 펼쳐 보관 | `04_input_archives/InvitesLoop_Chat_Only_Verified_20261030.zip` |

이번 입력은 DOCX/PPTX를 MD로 변환한 자료가 아니다. 두 바이너리 원본을 그대로 추가했다. 웹 URL은 파일 첨부로 계산하지 않는다. 이전에 Codex가 생성한 ZIP은 사용자 첨부와 구분하는 이력 산출물이다.

## 3 ChatGPT 기본 패키지의 11개 항목

아래 원문·생성 구분은 입력 패키지 README와 MANIFEST.csv의 설명에 따른다. 이전 ChatGPT 채팅 전체를 직접 열람해 업로드 이력을 재감사한 것은 아니다.

| 종류 | 파일 | 통합 위치 |
|---|---|---|
| 사용자 업로드 원문으로 분류 | 02_인바이츠루프 6대 지침.md | `01_chatgpt_baseline/01_user_uploaded_originals/02_인바이츠루프 6대 지침.md` |
| 사용자 업로드 원문으로 분류 | 04_인바이츠루프 3대 KPI.md | `01_chatgpt_baseline/01_user_uploaded_originals/04_인바이츠루프 3대 KPI.md` |
| 사용자 업로드 원문으로 분류 | 03_인바이츠루프 V5 프로토타입.md | `01_chatgpt_baseline/01_user_uploaded_originals/03_인바이츠루프 V5 프로토타입.md` |
| 해당 ChatGPT 대화 생성 문서로 분류 | InvitesLoop_V5_Competition_Analysis.md | `01_chatgpt_baseline/02_generated_in_this_chat/InvitesLoop_V5_Competition_Analysis.md` |
| 해당 ChatGPT 대화 생성 문서로 분류 | InvitesLoop_V5_Competition_Analysis_Updated.md | `01_chatgpt_baseline/02_generated_in_this_chat/InvitesLoop_V5_Competition_Analysis_Updated.md` |
| 해당 ChatGPT 대화 생성 문서로 분류 | InvitesLoop_3plus1_Strategy.md | `01_chatgpt_baseline/02_generated_in_this_chat/InvitesLoop_3plus1_Strategy.md` |
| 해당 ChatGPT 대화 생성 문서로 분류 | InvitesLoop_Codex_Competition_Handoff.md | `01_chatgpt_baseline/02_generated_in_this_chat/InvitesLoop_Codex_Competition_Handoff.md` |
| 해당 ChatGPT 대화 생성 문서로 분류 | InvitesLoop_Competition_20261030_Master_Handoff.md | `01_chatgpt_baseline/02_generated_in_this_chat/InvitesLoop_Competition_20261030_Master_Handoff.md` |
| 해당 ChatGPT 대화 생성 문서로 분류 | CHAT_CONTEXT_LATEST.md | `01_chatgpt_baseline/02_generated_in_this_chat/CHAT_CONTEXT_LATEST.md` |
| 패키지 범위·출처 메타데이터 | README_SCOPE_AND_MISSING_FILES.md | `01_chatgpt_baseline/README_SCOPE_AND_MISSING_FILES.md` |
| 패키지 범위·출처 메타데이터 | MANIFEST.csv | `01_chatgpt_baseline/MANIFEST.csv` |

한글 경로는 통합 패키지에서 NFC로 정규화했다. 내용 바이트는 바꾸지 않았고, 원래 ZIP 내부 경로는 통합 MANIFEST.json에 기록했다. 원래 MANIFEST.csv의 경로와 원전은 함께 보관된 입력 ZIP에서 그대로 재확인할 수 있다.

## 4 Codex에서 추가된 자료와 작성물

| 종류 | 파일 | 통합 위치 |
|---|---|---|
| 이전 Codex 패키지 안내·매니페스트 | README.md | `03_packaging_history/codex_previous/README.md` |
| Codex 첨부 원본 | 인바이츠루프_chronology(v6)_20261028.pptx | `02_codex_sources/인바이츠루프_chronology(v6)_20261028.pptx` |
| Codex 첨부 원본 | AI_운동처방_전문가_자문회의록.docx | `02_codex_sources/AI_운동처방_전문가_자문회의록.docx` |
| Codex 분석·이전 정리본 | InvitesLoop_Latest_Request_Handoff_20261030.md | `docs/InvitesLoop_Latest_Request_Handoff_20261030.md` |
| Codex 분석·이전 정리본 | InvitesLoop_Attachment_Reference_Inventory_20261030.md | `docs/InvitesLoop_Attachment_Reference_Inventory_20261030.md` |
| Codex 분석·이전 정리본 | UX_UI_Content_Strategy_v2_20261029.md | `docs/UX_UI_Content_Strategy_v2_20261029.md` |
| Codex 분석·이전 정리본 | UX_UI_Concept_Comparison_Criteria_20261029.md | `docs/UX_UI_Concept_Comparison_Criteria_20261029.md` |
| Codex 분석·이전 정리본 | UX_UI_Research_Requirements_and_Multisource_Analysis_20261029.md | `docs/UX_UI_Research_Requirements_and_Multisource_Analysis_20261029.md` |
| 이전 Codex 패키지 안내·매니페스트 | MANIFEST.json | `03_packaging_history/codex_previous/MANIFEST.json` |

과거 Codex 요청 통합본·목록은 새로운 입력을 받기 전 상태의 원문이다. 그 안의 ‘참고자료 4개 확인·12개 미확인’은 이력으로 보존하며 현재 상태는 아래 6절을 따른다.

## 5 두 입력에서 동일한 자료 5개

| 파일 | 동일성 | 대표 보관 위치 |
|---|---|---|
| InvitesLoop_Codex_Competition_Handoff.md | SHA-256 일치 | `01_chatgpt_baseline/02_generated_in_this_chat/InvitesLoop_Codex_Competition_Handoff.md` |
| InvitesLoop_V5_Competition_Analysis_Updated.md | SHA-256 일치 | `01_chatgpt_baseline/02_generated_in_this_chat/InvitesLoop_V5_Competition_Analysis_Updated.md` |
| 02_인바이츠루프 6대 지침.md | SHA-256 일치 | `01_chatgpt_baseline/01_user_uploaded_originals/02_인바이츠루프 6대 지침.md` |
| 03_인바이츠루프 V5 프로토타입.md | SHA-256 일치 | `01_chatgpt_baseline/01_user_uploaded_originals/03_인바이츠루프 V5 프로토타입.md` |
| 04_인바이츠루프 3대 KPI.md | SHA-256 일치 | `01_chatgpt_baseline/01_user_uploaded_originals/04_인바이츠루프 3대 KPI.md` |

원문의 이력을 지우지 않고 매니페스트의 origins에 두 컨테이너와 내부 경로를 기록했다. 같은 파일명이라는 이유만으로 중복 제거하지 않았다. 중복 5개는 내용까지 일치했다.

## 6 최초 Handoff 참고목록 16개와 현재 확보 상태

| 번호 | 파일명 | 최신 상태 |
|---|---|---|
| 1 | 00_SiBC_Project_Instructions(2).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 2 | 01_SiBC_DataScience_Handbook(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 3 | 02_SiBC_Data_Quality_Framework(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 4 | 03_SiBC_Reliability_Model(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 5 | 04_SiBC_Health_Check_Prediction_Model(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 6 | 05_SiBC_Clinical_Layer_Evidence_Validation(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 7 | 06_SiBC_Behavior_Layer_Evidence_Validation(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 8 | 09_SiBC_Model_Validation_Framework(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 9 | 11_SiBC_AI_Working_Principles(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 10 | 13_SiBC_Regulatory_Considerations(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 11 | 14_SiBC_Terminology_and_Status_Dictionary(1).md | 원문 미확인. Handoff의 파일명만 확인됐으며 포함하지 않음. |
| 12 | InvitesLoop_V5_Competition_Analysis_Updated.md | 이전 Codex와 이번 기본 자료에서 실물 확인. |
| 13 | InvitesLoop_3plus1_Strategy.md | 이번 입력 ZIP에서 새로 확보. 이전 미발견 상태 해소. |
| 14 | 02_인바이츠루프 6대 지침.md | 이전 Codex와 이번 기본 자료에서 실물 확인. |
| 15 | 03_인바이츠루프 V5 프로토타입.md | 이전 Codex와 이번 기본 자료에서 실물 확인. |
| 16 | 04_인바이츠루프 3대 KPI.md | 이전 Codex와 이번 기본 자료에서 실물 확인. |

현재 5개 확보·11개 원문 미확인이다. 앞선 로컬 검색 범위는 Downloads와 Documents/SiBC의 Markdown 파일이며, 이번에는 두 ZIP의 실제 항목도 추가 대조했다. 다른 위치·형식의 자료가 없다고 단정하지 않는다.

입력 README의 ‘이전 ZIP에서 제외한 SiBC 공통 문서 20개’와 이 Handoff의 ‘원문 미확인 11개’는 같은 목록이라고 입증되지 않았다. 20개에 대한 개별 파일명·원전은 이 입력에 없으므로 복원·첨부·열람했다고 주장하지 않는다.

## 7 별도로 참고했지만 직접 첨부가 아닌 로컬 자산

이 자료들은 이전 Codex 심화 분석에서 관련 내용을 참고했으며 통합 패키지에 새로 복사하지 않았다. 현재 DB·API·모델 성능을 재검증한 것이 아니다.

- `SiBC_project/README.md`
- `dietary_analysis_model/README.md`
- `dietary_analysis_model/docs/system_design_20261022.md`
- `medical_checkup_model/README.md`
- `medical_checkup_model/configs/schema.yaml`
- `SiBC_lifestyle_pattern_questions_v4_2026-08-12.md`
- `SiBC_Health_Data_SDK_Lifelog_통합_고도화_분석_20260731.md`
- `clinical_validation_model/docs/data_contract.md`

상세 로컬 경로와 검토 범위는 [심화 분석](UX_UI_Research_Requirements_and_Multisource_Analysis_20261029.md)에 남아 있다. 다른 컴퓨터에서는 로컬 절대 경로 링크가 열리지 않을 수 있다. 원시 식사·검진·웨어러블 데이터, DB 덤프, 환경변수·인증정보는 포함하지 않았다.

## 8 URL과 언급만 된 자료

- 사용자 제공 URL: [VISTA EBITDA 모델 V4](https://ksyoo-hconnect.github.io/ebitda/vista_v4.html). 이전에 페이지 내용을 분석했으며 이번에는 링크를 보존한다. 사이트 전체를 오프라인 복제하지 않았다.
- 공개 UX·AI 제품·WHO·NMPA·NHS·GOV.UK·HL7 자료: 분석 문서의 근거 링크를 보존. 원문 일괄 다운로드는 하지 않음.
- 원 V5 HTML, Claude 프로토타입 링크, H1 패치·시험 로그, 별첨 세계관 원문, 실제 API·운영 DB·기기·로봇: 문서의 언급이나 요약과 실물 확보·검증을 구분.
- CHAT_CONTEXT_LATEST.md는 이전 채팅 본문의 요약. 전체 채팅 원문·별도 업로드 원문과 동일하지 않음.

## 9 새 통합 문서와 읽기 순서

1. [통합 요청사항과 진행 방향](InvitesLoop_Integrated_Project_Brief_20261030.md)
2. [통합·변경 판단표](InvitesLoop_Integration_Decisions_20261030.md)
3. 본 통합 자료 목록
4. Codex의 콘텐츠 분석·다중 데이터 심화 분석·시안 비교 기준
5. ChatGPT 기본 자료와 이전 Codex 정리본은 출처·변경 이력 참고

## 10 패키지 구성과 보존

| 경로 | 파일 수 | 내용 |
|---|---:|---|
| `01_chatgpt_baseline/` | 11 | 기본 패키지의 모든 내부 파일 |
| `02_codex_sources/` | 2 | 회장님 PPTX와 운동 자문 DOCX 원본 |
| `docs/` | 8 | 기존 Codex 문서 5개와 새 통합 문서 3개 |
| `03_packaging_history/` | 2 | 이전 Codex 패키지의 README·매니페스트 |
| `04_input_archives/` | 1 | 이번 입력 ZIP 원본 |
| 최상위 README·MANIFEST | 2 | 현재 읽기 순서·출처·해시·중복 관계 |
| 합계 | 26 | |

과거 원문 20개와 입력 ZIP은 내용 바이트를 그대로 보존한다. 새 통합 문서만 현재 해석과 지침을 정리한다. 동일성 대조와 압축 검사를 통과해도 실제 의료·재무 효과와 사용성이 검증된 것은 아니다.
