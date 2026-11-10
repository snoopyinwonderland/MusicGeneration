# 검수 요청: 모티프 입력·기능 화성·작곡가 참조

- 브랜치: `codex/motif-studio-harmony`
- worktree: `K:\MusicGeneration\motif-studio`
- 기준: `origin/main` 72ca816에서 생성 후, 선행 꾸러미 8b8d7f7을 a8ae025로 cherry-pick. 이전 blueprint 꾸러미에 의존하며 main 병합을 대신하지 않습니다.
- main 및 Music Composition/Music Analysis의 코드·악보는 수정하지 않았습니다.

## 요청과 변경

사용자는 모티프 입력 화면, 증6화음·세컨더리 화음·전조, 작곡가 자료를 통한 모티프 발전을 요청했습니다. 현재 대화에서 작곡 설계를 작성하는 흐름을 유지하면서 다음을 추가했습니다.

| 파일 | 역할 |
|---|---|
| `musigen/studio.py`, `studio.html`, `studio.js`, `studio.css` | 입력·구간 선택·미리듣기·조건 지정·로컬 대기함. `studio --out … --port 8794` |
| `musigen/composer_reference.py` | 선택한 작곡가의 기존 DCML 적격 train 마디만 인덱스/검색. 프레이즈·종지·출처와 앞뒤 마디 ID 유지 |
| `musigen/functional_harmony.py` | 명시적 기능 기호와 구성음·철자 변환. 부속화음 목표와 증6화음 경향음 기록/부분 검사 |
| `musigen/blueprint.py` | 국소 조성과 조표 출력·재읽기, 기능 화음, 상세 sidecar 연결 |
| `musigen/blueprint_pages.py`, `listen_template.html` | 국소 조성 표·기능 증6화음 표시. symbol_display 없는 기존 페이지 표기 방식 유지 |
| `tests/test_studio.py`, `test_functional_harmony.py`, `test_composer_reference.py` | 요청 보존/분리, 화음 철자·전위·조성 교환, 성부 옥타브별 증6 해결, 데이터 분할·작곡가·박자 필터 |
| README, MOTIF_STUDIO, MOTIF_HARMONY_BLUEPRINT, RAW_CLASSICAL_SCORES | 실행·완료/미구현 범위·데이터 확인 결과 |

## 확인 결과

- 전체 unittest **111개 통과**. 기존 after_rain 출력 회귀 포함. JS 구문 검사, git diff --check 통과.
- [입력 화면](http://127.0.0.1:8794/): JSON 입력, 오류 시 이전 clip 무효화, MusicXML 성부·구간 선택, 선행 쉼 보존, 피아노 샘플 재생 완료, 로컬 요청 저장 확인.
- 모차르트 선택 후 저장한 UI 검증 요청에서 해당 작곡가 train 2,572마디와 4/4 온마디 434개 참조 풀 확인. 요청 2개는 개발 검증 자료이며 `status.json`에 `completed_ui_test_not_user_request`로 구분합니다.
- 다른 Origin의 POST 403, 같은 Origin의 잘못된 요청 400 확인. 요청 파일명은 UUID로 생성하고 출력 루트 밖 경로를 받지 않습니다.
- 실제 좁은 화면 452px에서 grid 최소 크기 때문에 페이지가 498px로 넘치는 문제를 수정. 수정 후 scrollWidth=clientWidth=452. 악보 자체만 내부 가로 스크롤을 사용합니다.
- [화성 교환 검증용 8마디](http://127.0.0.1:8794/harmony-demo/melody_harmony.html): 선율 27음, 화성 10이벤트, C–G–C 세 조성 영역 재읽기 일치. 검사 오류·경고 0. 음악적 품질 인증은 아닙니다.
- 화성 청취 위치: 2–3마디 D7(V7/V)→G, 4마디 Ger+6→C/G, 5–6마디 G장조, 7–8마디 C장조 회귀. 4마디 왼손 Ab2→G2, F#3→G3 두 반음 해결을 실제 옥타브로 확인. PDF는 이 기술 검증 예제에서 별도 생성하지 않았습니다.
- 브라우저의 Ger⁺⁶, V⁷/V, 조성별 I/V⁷ 표시 확인. MusicXML의 증6화음은 Italian/French/German 원형을 사용합니다.

## 자료 확인

기존 고전 반주 라이브러리를 다시 읽어 Mozart 2,572 / Beethoven 3,822 / Chopin 992 train 마디 확인. 현재 Chopin 참조는 마주르카입니다. 원 XML 폴더 208파일은 별도로 내용까지 확인했고 207개가 정상 파싱됩니다. Beethoven Op.31 No.3 1악장 파일 하나는 확장자는 XML이지만 SIBELIUS 헤더 바이너리입니다. 중복·기보 지문·화성 기호 유무는 RAW_CLASSICAL_SCORES에 기록했습니다.

## 완료와 한계

완료: 입력/저장/미리듣기, 명시적 기능 화음·조성 교환, 작곡가별 참고 검색, 원 XML 폴더 구조 확인.

미구현: 모티프만으로 완성곡 자동 작곡, 신경망 학습, 검색 사례를 자동으로 프레이즈로 발전시키는 모델, 원 XML 폴더의 새 패턴 라이브러리, utf8 전체 스타일 분석. 사용자 후속 요청의 utf8 자료는 별도 꾸러미로 진행합니다.

- `preferences.tempo`는 4분음표/분. 6/8의 기존 design.tempo와 단위를 구분합니다.
- function/cadence/functional_intent는 작곡자 의도. 검사 범위는 명시적 XML 교환, 다음 목표 근음/베이스와 증6 두 경향음의 반음 이동입니다. 전체 성부·전조 확립·종지 검증이 아닙니다.
- musicomp는 기능 sidecar를 아직 소비하지 않습니다. 이번 고급 화성은 상세 화성 악보까지 검증했고 고급 화성의 독주 실현·기능 라벨 보존은 별도 확인이 필요합니다.
- DCML 선택은 비상업(CC BY-NC-SA 4.0) 자료의 명시적 opt-in. 데이터를 git에 넣지 않습니다. 조회 거리는 잠정이며 첫 마디의 밀도·쉼·작은 음정 비율만 사용합니다. 학습된 스타일 품질 점수가 아닙니다.
- 모든 UI 시험 입력과 반환 파일은 output 아래에만 보관하고 실제 사용자 작곡 요청으로 처리하지 않습니다.

## 다음 순서

사용자가 추가한 utf8 자료의 작곡가·편성·시대/활동 지역 정보와 리듬·성부 통계를 별도 꾸러미에서 정리합니다. 이후 사람이 검수한 2·4·8마디 연결 및 주제 변형 설계로 확장합니다. 평가용 작품을 참조에 넣거나 불확실 선율/화성을 정답으로 채우지 않습니다.
