# P1 검수 요청: 모티프 후보 비교와 명시적 선택 기록

- 브랜치: `codex/motif-candidates`, 기준 origin/main `b2b06cd`.
- 요청 문서: `docs/handoff/2026-10-24_MOTIF_PHRASE_DEVELOPMENT.md` P1, P5.
- 상태: 구현·기술 검증 완료, 두 설계의 8개 후보 제공 / 4/4 m5·3/4 m6 실제 사용자 선택 반영. P2–P4 완료로 간주하지 않음.
- main 미수정·미push. 기존 piece 경로·기존 예시 악보 출력 미변경. 새 명령으로만 사용.

## 변경 이유와 파일

사용자 의견: “작곡은 아직 수준이 기대에 못 미치네요. 모티프와 프레이즈를 만들어서 발전시키는 과정이 부족하다고 느낍니다.”

- `musigen/motif_candidates.py`: settings, rhythms, generated, features, preview, generate, run. 리듬 세포·윤곽 조합의 유한 검색, 실제 시작 위치/윤곽 중복 제외, 설계·기존 급수 검사, 기존 realise 응답, 공통 블록 반주, 출처/특징/진단/원음 및 XML을 로컬 저장.
- `musigen/candidate_page.py`, `candidate_template.html`, `candidate_player.js`: 한국어 비교 페이지, 같은 피아노·빠르기·반주 재생, 반복/연속/두 후보 교대, 선택 및 이유 보관·내보내기. 직접 두 마디의 Note 사건을 재생하며 페달 없음.
- `musigen/selections.py`: choose. 설계 및 후보 지문·id·shown·이유를 확인한 후에만 JSONL 추가 기록과 selected_motif.json 생성. 수정된 후보·이전 export·다른 설계를 거절. 자동 선택 없음.
- `musigen/__main__.py`: motifs, choose 명령만 추가.
- `examples/stages/lyrical_34/design.json`, `bright_44/design.json`: 두 시험 설계. 원음 악보 없음.
- `tests/test_motif_candidates.py`: 13개 테스트 추가.
- `docs/MOTIF_CANDIDATES.md`, `docs/COMPOSING.md`: 사용법·범위·잠정 기준·제한.

## 전후 결과와 사용자 선택 위치

이전에는 하나의 악보로 바로 진행했으며 후보 비교·선택 기록 경로가 없었습니다. 현재는 모티프 8개를 먼저 듣고 사용자가 고른 것만 다음 단계 입력으로 저장할 수 있습니다.

| 설계 | 결과 | 실제 서로 다른 리듬 지문 / 윤곽 유형 | 탐색 시도 |
|---|---|---|---|
| 서정적 F장조 3/4, 72, 6급 | 8/8 | 8 / 8 | 8 / 320 |
| 밝은 C장조 4/4 당김음, 100, 6급 | 8/8 | 8 / 8 | 12 / 320 |

- 서정적 비교: http://127.0.0.1:8792/lyrical_34/stage1_motifs/index.html
- 밝은 당김음 비교: http://127.0.0.1:8792/bright_44/stage1_motifs/index.html
- 로컬: `K:\Music Generation-codex\output\motif-candidates\<설계>\stage1_motifs`
- 두 페이지 모두 후보 **m1–m8의 1마디 주제와 2마디 응답**을 비교하여 각각 하나 선택. 이걸로 → 이유 → 선택 내보내기. 대화로 설계별 id를 알려 줘도 명시적 choose 가능.
- 후보 전체 음역 C4–A5, 모든 2마디 맛보기가 기존 급수 연주 오류 0. 최종 페이지의 원음과 source/provenance는 candidates.json 및 runs/<set_id> 아래 저장.
- 기본 반복 응답은 공통 V 화음으로 열린 문장이라 완성곡 검사에서 종결 경고가 있음. 원래 경고를 보존하며 품질 점수/후보 탈락 기준으로 쓰지 않음.

## 검증

- 테스트 전 91개 → 후 **104개 통과**. 기존 `ExpressionTest.test_legacy_bytes`의 after_rain 기준 MusicXML과 바이트 일치 통과.
- 동일 설계/seed의 동일 데이터, 실측 리듬/윤곽 중복 없음, 강박 생성음이 으뜸화음 구성음, 모든 오른손/응답 음역과 공통 왼손 확인.
- 장조 두 설계 외 단조·1급에서도 명시 조성/급수 보존·공통 Am→E 반주 및 1급 단음 한도 확인.
- composer/import 음·쉼·출처 보존; 긴/다성/범위 밖 입력은 거절. 좁은 음역에서 제한된 탐색 후 stopped 및 choose 거절 확인.
- 선택 이전에는 selected_motif.json·selections.jsonl을 만들지 않음. 잘못된 id/shown/이유/지문·변경 설계 거절, 유효 선택의 JSONL 누적 및 정확한 다음 단계 입력 확인.
- 브라우저 두 설계: Verovio/JS 오류 0, 악보 8개씩, 피아노 재생·정지·반복·교대·연속 재생, 세 번째 교대 체크 거절, 선택 내보내기·다시 열기 복원, 390px 가로 넘침 없음.
- 오프라인 렌더한 m1 샘플: 서정적 peak 0.1842/RMS 0.02309, 밝은 peak 0.1763/RMS 0.02519; 클리핑 없음. 실제 사용자 청취 평가가 아님.
- 브라우저가 내보낸 파일을 별도 qa/choose-integration 폴더에서 실제 CLI choose로 읽어 검증. 이유에 “실제 사용자 선택 아님” 표기. 사용자 작업 폴더에는 테스트 선택이 섞이지 않음.
- 근거: `output/motif-candidates/qa/browser.json`, PNG, `*-test-selection.json`, `*-choose-result.json`, `browser_qa.cjs`.

## 기준값과 중단

- 6–10개 후보와 6개 미만 중단은 요청 문서 기준. 320번 상한, 4–8음, 리듬 세포·윤곽 재료, 당김음 정의는 **잠정**. 음악적 우수성 판정값 아님.
- 처음 4/4는 조건 밖 리듬에도 시도를 소모해 7개였음. 새 규칙·계수/상한을 더하지 않고 기존 목록을 시작 박·당김음 조건으로 먼저 필터링하여 8개 생성. 6개 미만 중단 기준에는 걸리지 않음.
- 윤곽은 실제 음높이 차의 방향열을 연속 압축한 유형. 혼합형도 정확한 방향열로 구별하고 한국어로 표시. 청각적 개성이나 문장 기능이 서로 다르다는 증거는 아님.

## 한계와 다음 입력

- 현재 3/4·4/4 한 마디 단선율. pickup/swing은 명시적으로 거절. 기존 전체 piece 지원 범위를 줄인 것은 아님.
- impression은 보존·표시되는 작곡 맥락이며 자유 문장을 자동 해석하는 모델은 연결하지 않음. 리듬과 윤곽은 새 잠정 재료이고 아직 P3 통계가 아님.
- 후보가 모두 마음에 들지 않으면 선호 곡/직접 쓴 짧은 모티프 또는 리듬 조건이 더 필요함. 점수를 높이려는 반복 규칙 확장 없이 판단을 받음.
- 사용자의 실제 두 모티프 선택이 있어야 문서의 P2 시험 및 다음 단계 입력으로 진행. 4/4 m5와 3/4 m6을 반영함. 사용자 대신 임의 선택 이력을 만들지 않음.
- P1은 출처 표시 비교. P4 눈가림은 구현되지 않았으며 뒤 단계 과제.
- 이 단계는 정적 페이지라 서버에 선택을 쓰지 않음. 로컬 저장은 브라우저별이며 JSON 내보내기/CLI 반영 필요. 이전 후보 묶음은 runs에 보존.

## 실제 사용자 선택 반영

- 밝은 4/4: **m5**, 이유 원문: “리듬이 괜찮네요. 멜로디는 큰 특색은 없지만.”
- 실제 브라우저 표시와 사용자가 내려받은 motif-selection.json을 대조. QA의 m3는 사용자 선택이 아님.
- 사용자가 열어 둔 이전 묶음과 최신 묶음의 차이는 contour_label·range 표시 필드뿐임을 전체 후보 데이터로 확인. 원본 export와 검증 이력을 로컬 user_selection/에 보존한 후 동일 음악의 현재 묶음으로 choose 실행. CLI의 임의 stale export 거절 정책은 변경하지 않음.
- selected_motif.json 및 selections.jsonl에 기록. 3/4는 대화에서 m6으로 확정하여 choose로 기록.

