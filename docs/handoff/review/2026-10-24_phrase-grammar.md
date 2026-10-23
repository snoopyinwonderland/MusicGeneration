# P2 검수 요청: 프레이즈 기능 문법과 후보 비교

- 브랜치: `codex/phrase-grammar`, origin/main `b2b06cd`에서 시작. P1 `1efcace`를 의존 커밋 `c2b6a24`로 cherry-pick함. P1 검수·병합 뒤 이 브랜치의 P2 변경을 검수할 것.
- 구현·기술 검증 완료, 실제 프레이즈 선택 및 16마디 검수곡 생성 대기. P2 전체 완료·음악적 향상으로 간주하지 않음.
- main 미수정·미push. 기존 악보 출력은 바꾸지 않고 새 phrase 필드·phrases 명령에서만 사용.

## 변경과 근거

- `musigen/phrase_grammar.py`: 명시적인 8마디 sentence/period/hybrid 확장, 기존 realise/apply 및 반주 음형, 마디별 기존 재료 덮어쓰기, 실제 출력 음표·화음 기반 기능 검사.
- `musigen/phrase_candidates.py`: P1 실제 선택과 보존 묶음·설계 지문 검증, 4개 후보 및 8마디 MusicXML·분석 결과.
- `musigen/phrase_selection.py`: P2 선택 JSONL과 다음 piece 작업 폴더. 선택한 8마디+반주를 바꾼 8마디 재현 초안.
- `musigen/piece.py`: phrase 블록만 확장, 직접 motif JSON 성부 지원. 기존 블록은 그대로 처리.
- `musigen/checks.py`: 명시적인 phrase가 있을 때만 기능 관찰 추가.
- `musigen/selections.py`, `__main__.py`: 단계별 명령 라우팅.
- 비교 페이지: 단계·박자 크게 표시, 후보 개수를 박자와 다른 형식으로 표기, 8마디 여러 줄 악보 및 기능 검사 접기.
- `tests/test_phrase_grammar.py`: 12개 추가 테스트. `docs/PHRASE_GRAMMAR.md`: 사용법·제한·근거.

구조는 Caplin, *Classical Form*(1998), 3–5장과 [저자 설명](https://www.music.mcgill.ca/~caplin/teaching-classical-form.pdf)을 참고. 반 마디 단위, 리듬 세포 처리, 한 옥타브 블록 배치, 수치 기준은 잠정 작곡 선택이며 실곡 통계가 아님.

## 비교 결과와 검증

- 입력: 사용자 선택 **3/4 m6**, **4/4 m5**. 4/4 의견 원문: “리듬이 괜찮네요. 멜로디는 큰 특색은 없지만.”
- 이전: 모티프 1마디+공통 응답 1마디. 이후: 각 입력에서 8마디 프레이즈 4개. p1 문장형 조각·순차 진행 / p2 악절형 / p3 혼합형 / p4 문장형 리듬 축소.
- [3/4 비교](http://127.0.0.1:8792/lyrical_34/stage2_phrases/index.html), [4/4 비교](http://127.0.0.1:8792/bright_44/stage2_phrases/index.html).
- 로컬 `output/motif-candidates/<설계>/stage2_phrases/runs/<set_id>/p1..p4`: score/design/checks/preview.musicxml.
- 104 → **116개 전체 테스트 통과**, 기존 after_rain MusicXML 바이트 회귀 통과. 두 박자의 세 유형, 원 모티프의 음·쉼 보존, 기능 경계, 종지, 실제 덮어쓰기 이후 불일치 탐지, 선택 지문과 16마디 연결 검증.
- 실제 IAB: 두 페이지 악보 4개씩, Verovio/JS 경고·오류 0, 3/4 p1 재생 상태 확인, 악보 줄바꿈·큰 박자 안내 육안 확인. P2 모바일 390px 실측은 아직 하지 않음(P1의 동일 반응형 CSS 검증과 구분).
- 모든 후보의 기존 연주 오류 0. 공통 block의 원래 16반음 배치가 6급 한도를 넘어서, phrase 경로에서만 기존 패턴을 한 옥타브 안으로 재배치함.
- continuation의 단위 축소는 명시적 구성 단위 기준이며 자동 분절 정확도를 검증한 결과가 아님. 종지와 악절형 반복은 실제 출력 비교.

## 자기 검토와 남은 일

- 리듬·쉼은 선택 모티프에서 유지되나 화음 구성음으로 옮긴 반복과 짧은 순차 진행이 도드라짐. 구조 검사는 통과해도 선율의 개성이 향상됐다고 말할 수 없음.
- 16마디 연결은 동일 악상의 반주 변화 재현이라 대조부가 제한적임. 반복 기법을 더 추가하는 실험은 여기서 하지 않음. 사용자 청취 및 P3·P4 결과로 판단.
- 실제 선택 프레이즈의 곡 출력은 대기 중. 테스트용 p1/p2 선택은 임시 폴더에만 있으며 실제 사용자 기록에 섞이지 않음.
- P3 통계·P4 모델은 아직 이 브랜치에 연결하지 않음. 프레이즈 후보는 opt-in, 품질 검증·기본 적용 아님.
