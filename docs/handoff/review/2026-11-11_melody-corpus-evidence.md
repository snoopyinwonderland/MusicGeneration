# 검수 요청: M1 주선율 자료 조사와 관찰 근거

- 브랜치 `codex/melody-corpus-evidence`, 작업 트리 `K:/MusicGeneration/melody-research`.
- origin/main `72ca816`에서 선행 19개 커밋을 가져온 `95cd3e2` 다음 변경이다. 이전 작업 내용을 중복 병합하지 않도록 이번 커밋을 구분해 검수한다. main에는 커밋·push하지 않는다.
- 사용자 요청: 남은 계획을 재정리하고, 전체 보유 자료와 인기곡의 선율 특징을 참고해 다섯 새 곡을 만든다. 후속 원문 “반복을 기계적으로 배제할 필요는 없고 적당한 자리에서 주제의 반복으로 써도 됩니다. 다만 너무 단순해지는 것은 피하라는 것이었습니다.”를 우선했다.

## 변경과 이유

자료 목록만으로는 실제 주선율을 읽었는지 알 수 없었다. 파일의 처리 상태, 역할이 확인된 선율, 미확정 성부, 중복과 분모를 분리한 선택 실행 도구를 추가했다. 원본과 기존 생성 기본값·학습 계수는 수정하지 않는다.

- `musigen/corpus_features.py`: `midi_features(include_notes=False)`. 기본 반환은 유지하고 명시적으로 요청한 경우 음 사건과 가사 tick만 반환한다. 가사 본문은 반환하지 않는다.
- `musigen/melody_inventory.py`: `extend`. 기존 69개 루트에 사용 허용된 KYSing 원본 MIDI·리드시트 경로를 선택 추가. 반복 실행 중복 추가 방지.
- `musigen/melody_evidence.py`: `xml_lines`, `midi_lines`, `kern_lines`, `line`, `features`, `inspect_file`, `run`. 단성 성부 추출, 역할 근거, 시간·음정 사실, 바이트/전체 선율 중복, 재개 가능한 DB와 파일별 오류 보고.
- `musigen/melody_annotated.py`: `mtc_record`, `weimar_record`, `run`. 주석형 자료의 명시 선율을 별도 레코드 분모로 읽는다. MTC의 IOI와 Weimar의 초 단위를 구별한다.
- `musigen/melody_profile.py`: `summarize`, `run`. 중복된 성부의 명시 역할 우선, 역할·출처별 관찰. 품질 점수나 자동 프레이즈 정답이 아니다.
- `tests/test_corpus_catalog.py`, `tests/test_melody_evidence.py`, `tests/test_melody_annotated.py`: MIDI 기본 동작/선택 출력, 실제 사건과 지문, 붙임줄·다성부 거절, 제외 사유, 목록 재실행, 역할 우선, 바이트 캐시와 수정 파일, 주석 시간 단위.
- `docs/MELODY_RESEARCH_PLAN.md`, `MELODY_EVIDENCE.md`, `CHART_MELODY_COHORT.md`, `MELODY_OBSERVATIONS_2026-11-11.md`: 계획·재실행·한계·출처·실측 결과. M2/M3의 최종 산출물 결과도 관찰 문서에 연결한다.

## 결과와 검증

전체 처리 수·역할별 분모·오류·차트 연결 수치는 [관찰 결과](../../MELODY_OBSERVATIONS_2026-11-11.md)에 동결했다. 등록 자료의 지원 대상은 끝까지 처리했으며, 실패를 성공 선율 수에 넣지 않았다. `remaining_eligible=0`을 완료 조건으로 사용했다.

KYSing MIDI 32개를 일정 간격으로 골라 Composition의 독립 SMF 읽기와 대조: 시작·끝·음높이·PPQ 32/32 동일. 전체 MIDI 파서 정확도 인증으로 확대하지 않는다. 원본 문서와 제목·가수/작곡자·실제 성부가 확인된 TJ 8곡/캐나다 Billboard 7곡만 연결했다. 클래식 인기곡 주선율 연결은 미확정으로 남긴다.

M1–M3 최종 통합 253개 테스트 통과. 기존 after_rain 직접 출력 SHA-256 `9250d61a0e3f171ca1bf5c444fe75523e9c468cfeabdaa4c869a2a87b3ef1afc` 불변. 근거는 `output/final-tests.log`, `output/ky-parser-crosscheck.json`, 각 JSON 보고서다. M1은 생성 출력을 바꾸지 않으며, 듣기 비교는 M3에 있다.

## 위험과 적용 상태

KYSing은 Composition `DEVELOPMENT_LOG.md` #175의 2026-11-09–10 사용자 허용을 확인했다. AGENTS의 ‘권한 확인까지 보류’ 조건이 충족된 로컬 분석만 선택 실행했다. AI Hub 및 미확인 국악 자료는 제외한다. 코드 라이선스를 악곡 권리로 해석하지 않는다.

파트 이름·가사 요소는 주선율의 완전한 정답이 아니다. MIDI 겹침·연주 간격, MusicXML 기보음/반복 미전개, 지원하지 않는 kern 다성/동적 성부, 파일별 파서 오류를 명시한다. 기존 경로가 처리된 DB 재개는 원본 변경을 자동 추적하지 않으므로 새 원본판은 새 출력 폴더로 조사한다. 원음표·가사·생성물은 Git 제외 output에만 있다. 자동 P3/P4 재통과나 기본 채택은 아니다.
