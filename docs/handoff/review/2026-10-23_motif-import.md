# 보표 아래 화성 표시·모티프 가져오기 검수 요청

- 브랜치 `codex/motif-import`, 기준 `origin/main` `86b320f` (이전 프레이즈/RNA 꾸러미 검수 병합 후).
- musicomp main `c361a87`을 읽기만 사용. MusicAnalysis와 main 작업 파일 수정 없음.
- 상태: 구현·단위 검사·브라우저·CLI 연결 검증 완료. Claude 병합과 사용자 사용성 검수 대기.

## 사용자 요청

“화성 기호 staff 밑에 표시되면 좋겠네요. 혹시 Motif를 입력 받아서 발전시키는 작곡도 될까요. 모티프를 다른 musicxml 등 악보를 열어서 구간을 선택해서 클립보드 등에 복사해 두고 그걸 불러다 붙여넣는 방식도 되면 좋겠습니다.”

## 변경과 범위

1. 화성 위치: 듣기 페이지의 초기 선택을 ‘보표 아래’로 제공하고 ‘원래 위치’를 선택할 수 있게 했다. Verovio의 표시용 MEI에서 harm의 place/staff를 설정해 피아노 낮은 보표 밑으로 옮긴다. 코드 심벌과 Roman Numeral Analysis 모두 적용한다. 악보 음표·리듬·페달은 유지한다. **이 배치는 화면용이며 다운로드 XML/PDF는 원본 그대로다.**
2. 모티프 작업실: MusicXML 파일/텍스트/현재 악보 열기 → 파트·보표·성부 선택 → 시작·끝 사건을 선택 상자 또는 실제 악보 클릭으로 선택 → 강조 → 모티프 추출 → 피아노 듣기/복사/JSON 저장/다시 붙여넣기. JSON은 다른 페이지에서도 독립적으로 열 수 있다. 파일 내용은 서버로 보내지 않는다. 클립보드 접근은 명시적인 버튼에서만 하며 권한 거절 때 Ctrl+C/V 경로를 안내한다.
3. 가져온 재료: 기보 음높이와 철자, 분수 음가, 쉼. backup/forward로 분리된 성부를 구분하고 내부 붙임줄은 하나의 지속음으로 합친다. 잘린 붙임줄과 제외된 장식음을 안내한다. 출처 파일명·파트·보표·성부·마디·박 위치를 저장한다.
4. 작곡 연결: 복사 객체를 score.motifs에 넣을 수 있다. 기존 realise의 이조·역행·전위·음가 확대/축소·단편화·반복 진행을 그대로 사용한다. 새 `motif` CLI는 JSON을 받아 ops를 적용한 MusicXML/MIDI와 재사용할 motif.json, design/score.json을 만든다. 완성곡 자동 생성이나 외부 악보 프로그램의 전용 클립보드 호환을 주장하지 않는다.

## 바꾼 파일

| 파일 | 변경 |
|---|---|
| musigen/motif_tools.js | MusicXML 분수 시간 추출, 성부별 구간 선택, 클립 검증·복사·붙여넣기·다운로드·피아노 미리듣기 |
| musigen/motif_panel.html | 작업실 UI, 선택 강조와 반응형 입력 폭 |
| musigen/motif_clip.py | Python 교환 형식 검증, read_events/to_clip, 기존 연산을 사용하는 develop |
| musigen/piece.py | 선택 모티프 객체를 Ev로 읽기. 기존 문자열 경로 유지 |
| musigen/__main__.py | motif 명령 |
| musigen/listen_template.html | 보표 아래/원래 위치, 작업실 바로가기와 삽입 위치 |
| musigen/listen.py | 독립 HTML에도 작업실 코드 포함 |
| tests/test_motif_clip.py | 네 개의 회귀/검증 검사 |
| scripts/check_motif.cjs | 브라우저 실동작과 타이밍 픽스처 검증 |
| docs/listen, README, COMPOSING | 검수 페이지, 형식과 제한 설명 |

곡별 예외·화성 인식 계수·분석 임계값을 추가하지 않았다. 새 import/CLI는 명시적으로 사용하는 선택 기능이다. 화성 위치는 사용자 요청에 따라 이번 공개 페이지에서 아래가 초기 선택이며 원래 위치 복귀 가능하다.

## 검증 결과

- Python 68→72개 통과: 철자·화음·분수 쉼 왕복, 문자열 모티프와의 음표 동일성, 기존 이조/확대, 잘못된 형식·음가·중복음·무음 거부, 실제 XML/MIDI 생성과 기존 출력 폴더 덮어쓰기 거부. 기존 after_rain 바이트 회귀도 통과.
- Node 기존 재생 4개 통과.
- `scripts/check_listen.cjs`: 6곡 Verovio 로그/JS 오류 없음, RNA 전환과 기존 XML/PDF/WAV 버튼 정상. 배치 변경 뒤에도 음 수·60초 길이·페달·듀엣 파트 유지.
- `scripts/check_motif.cjs`: 실제 음표 클릭으로 솔로 첫 마디 F#4–A4–B4–A4와 1,1/2,1/2,1박을 추출. 클립보드 복사→비우기→붙여넣기, JSON 다운로드→파일 재열기, 모티프 재생/정지 확인. 위/아래 전환 전후 음높이·시각·길이 동일. 모바일 390px 가로 넘침 없음.
- 직접 만든 시험 MusicXML: 여린내기 F#4/0.5 + 쉼 0.5 + G4/0.5 + 마디를 넘는 A4 붙임줄 2+1 + Bb4/1/3 + C5/2/3 + 쉼 1 = 총 13/2박. 추출 JSON과 일치. 아래 보표의 C3은 섞이지 않았다. 경계 붙임줄은 안내하고 잘랐다.
- 브라우저에서 받은 a.motif.json을 `motif --ops step:1 aug:2 --key D --meter 3/4`로 실행: 첫 음 G4/2박, 총 6박·2마디 출력. 타이밍 시험 클립도 13/2박 그대로 출력하고 미리보기 악보만 마지막 마디 쉼으로 채웠다.
- 시각 확인: 아래 화성은 페달선 밑에서 분리되어 읽히며, 모바일 작업실의 긴 악보는 내부 스크롤한다. `output/motif-import/harmony-below.png`, motif-studio.png, motif-mobile.png, browser-check.json.

전후 곡 내용 변경 없음. 현재 솔로 `output/virtual-composer-release/lingering_light/v002`, 듀엣 `lingering_light_duet/v003` 유지. 실제 편집/변형 확인 결과는 `output/motif-import/developed` 및 `timing`. output 및 사용자 입력은 커밋하지 않았다. 공개 XML/PDF와 음원 자산도 바꾸지 않았다.

## 지원 경계와 남은 일

- 비압축 score-partwise MusicXML(.xml/.musicxml), 전용 모티프 JSON 지원. .mxl, timewise, 타악기/타브, 미분음, 복합 박자표 표기, 외부 앱 전용 클립보드, PDF/사진 인식은 지원하지 않는다.
- 1/12박보다 짧거나 기존 writer로 표현하지 못하는 음가를 반올림하지 않는다. 다섯잇단 등은 명확히 거부한다. 기보음 기준, 반복 미확장.
- 다른 길이의 화음음·부분 붙임줄 화음·겹친 성부는 손실을 감추지 않고 거부한다. 표현 기호는 이번 교환 형식에서 제외하고 새 곡에서 설계한다.
- 원곡 한 곡·합성 타이밍 악보의 동작을 확인한 것이며 모든 악보 프로그램의 내보내기 호환 시험은 아니다. 사용자 파일을 받아 추가 확인 필요.
- 웹은 구간 선택·보관·듣기까지, 실제 발전 연산은 기존 작곡 코드/CLI와 대화 작업에서 수행한다. 완성곡 생성 버튼은 만들지 않았다.
- 기존 PDF/XML에 화면 위치를 반영하는 별도 내보내기는 이번 범위에 포함하지 않았다. UI와 README에 명시했다.
- MEI 배치 근거: https://music-encoding.org/guidelines/dev/mei-basic/elements/harm.html 의 place/staff. 원본 XML 후처리를 하지 않는다.

## 검수

Claude 검수 대기. main 병합 후 공개 페이지의 작업실·클립보드 권한 거절 시 대체 경로와 실제 사용자 MusicXML을 확인해 주세요.

## 검수 (Claude, 2026-10-23)

**판정: 통과, main에 병합.**

- 테스트: Python 72개, Node 재생 4개 통과.
- 코드
  - 모티프 JSON 읽기는 `format: musicanote-motif`인 경우에만 쓰입니다. 기존 문자열 모티프 경로는 그대로입니다.
  - `motif` 명령은 기존 변형 연산을 재사용합니다.
- 병합 때 추가한 사용자 요청: "Roman Numeral과 Chord Symbols는 직전에 눌렀던 상태를 기억하게 해 주면 좋겠네요."
  - 화성 표기(코드 심벌·로마자)와 위치(보표 아래·원래 위치)를 브라우저 저장소에 기억합니다. 다른 곡으로 가거나 다시 방문해도 이어집니다.
  - 저장 키: `musicanote-harmony-mode`, `musicanote-harmony-place`.
  - 저장소를 쓸 수 없는 환경에서는 기본값으로 엽니다.
  - `listen_template.html`을 고쳤고, 공개 페이지 13개에 같은 변경을 반영했습니다.
    - 로마자 기능이 없던 옛 고정판(`lingering_light/v001`, `lingering_light_duet/v002`)은 그대로 둡니다.
  - 확인(Edge): 로마자·원래 위치로 바꾼 뒤 모퉁이 카페로 이동하면 로마자·원래 위치로 열립니다. 코드 심벌로 바꾸고 새로고침하면 코드 심벌로 열립니다. 오류 없음.
- 참고: 모티프 작업실 코드(약 18KB)가 페이지마다 들어갑니다. 공통 자산으로 빼면 저장소 증가가 줄어듭니다(다음 과제).