# 국소 조성 자료 검증과 모티프 발전 설계

2026-11-11 후속: `--verify-score-timing`으로 원 MuseScore XML 음표·화성 시각의 독립 대조를 추가했습니다. 고정 6개 모두 8,121음표·1,123주석 일치. 이전 두 제외는 대안 해석 열을 빠뜨린 검사 한계였으며 원자료를 고치지 않고 두 해석을 보존했습니다. 새 참조는 국소 조성 변화 17곳·일반 슬래시 으뜸화 159곳입니다. 아래 첫 결과 4/6은 당시 결과로 보존합니다. [독립 검증과 재현 명령](handoff/review/2026-11-11_tonal-timing-audit.md).

DCML의 명시적 국소 조성·세컨더리 화음 주석을 확인하고, 사람이 작성한 모티프 발전 설계의 실제 조성·화성과 연결하는 선택 기능입니다. 원 화성을 새로 인식하거나 전조를 자동 작곡하는 모델은 아닙니다. `--allow-dcml`로 관찰 자료를 만들고, 작곡 때 `--tonal-references`를 지정합니다. 기존 기본 출력은 유지합니다.

## 구별하는 정보

- `local_key_change`: 원 주석의 국소 조성 상태가 바뀐 곳. 앞 조성, 도착 조성, 그 상태가 유지되는 기보 구간을 보존합니다. 청취로 확정한 전조와 동일시하지 않습니다.
- `tonicization`: 원 화음에 명시된 `/V`, `/ii` 등의 향하는 조성. 현재 국소 조성과 별도입니다. 단조의 VI·VII는 자연단음계 기준으로 해석하고 철자를 보존합니다.
- 종지: 도착한 **국소 조성 구간** 안에 있는 원 종지 주석입니다. 세컨더리 화음의 목적 조성이 독립 조성이 되었다는 증거로 사용하지 않습니다.
- 증6화음: ms3는 It·Ger·Fr를 `/V` 특징을 가진 화음으로 확장합니다. 원 라벨에 없는 슬래시를 새 으뜸화 사례로 세지 않습니다. 이 구현은 이 세 원형의 확장을 확인하고 다른 특수 확장은 거부합니다.

해석 근거는 [DCML 표기 규격](https://dcmlab.github.io/standards/build/html/reference/reference.html), [ms3 시각·자료 설명](https://ms3.readthedocs.io/en/latest/manual/index.html), [ms3 특수화음 확장 코드](https://ms3.readthedocs.io/en/stable/_modules/ms3/expand_dcml.html)입니다.

## 검증 계약

각 작품의 harmonies·measures·notes TSV, MS3 MuseScore 원본, LICENSE, README를 읽고 경로와 SHA-256을 보존합니다. 원본은 수정하지 않습니다.

1. 마디 순번 MC, 인쇄 번호 MN, 박자, 실제 마디 길이, 음표·화성의 시작 좌표를 대조합니다. `mc_onset`은 온음표 단위이므로 4배 하여 4분음표 단위와 비교합니다.
2. 정확한 분수 음가를 보존합니다. 실수로 직렬화된 길이는 해당 좌표의 기계 반올림 오차만 허용합니다. 박 단위 양자화나 허용치를 넓혀 맞추지 않습니다.
3. 길이가 0인 프레이즈·종지 표시를 화음과 구분합니다. 그런 점 표시는 앞 화음의 울리는 구간을 끊지 않습니다.
4. 모든 원 화성 라벨이 MuseScore의 같은 MC/보표/성부에 같은 개수로 존재해야 합니다. TSV의 조성 상태·장단조·슬래시 목적·종지는 원 라벨에서 이어받은 값과 일치해야 합니다.
5. 하나라도 맞지 않으면 해당 작품 전체를 제외하고 사유를 남깁니다. 반복은 펼치지 않으며, 대체 종결 때문에 순차 기보 시계가 맞지 않는 자료도 지원하지 않습니다.

**범위 제한:** 음표 시각 검사는 TSV 내부의 음표/화성/마디표 교차 검사입니다. XML에서는 주석의 마디·보표·성부 주소를 확인하며 모든 음표 시각을 독립적으로 재해석하지 않습니다. 원 주석의 음악적 타당성, 전조의 청취 설득력, 종지 종류를 인증하지 않습니다.

`tools/verify_tonal_reference.py`는 원 파일 해시를 다시 읽고, 관찰된 서로 다른 조성 관계의 으뜸음 철자를 music21로 교차 확인합니다. 작곡 시에는 선택한 라이브러리 내용의 지문을 잠그며 원 파일을 매번 자동 재검사하지 않습니다. 자료가 바뀌었다면 관찰과 검증을 다시 실행하세요.

## 실행

저장소에서 지정된 Python 환경을 사용합니다. `output/`의 모든 원 주석·산출물은 Git에서 제외합니다.

```powershell
$env:MUSICOMP_ROOT = 'K:\Music Composition'
$py = 'K:\Music Analysis\.venv\Scripts\python.exe'
$corpusRoot = 'K:\MusicSearch\data\classical-corpora\dcmlab'
& $py -m musigen.tonal_reference --root $corpusRoot --allow-dcml --works mozart-sonatas/K279-1 mozart-sonatas/K279-2 beethoven-sonatas/01-1 beethoven-sonatas/01-2 chopin-mazurkas/BI105-2op30-2 chopin-mazurkas/BI105-3op30-3 --out output/tonal/library.json
& $py tools/verify_tonal_reference.py --root $corpusRoot --library output/tonal/library.json --out output/tonal/verification.json
& $py -m musigen.development_recipe --work output/my-input --out output/my-piece --tonal-references output/tonal/library.json --corpus-accompaniment
```

라이브러리와 검증 출력은 새 파일이어야 합니다. 작곡 입력의 `motif.json`, `recipe.json`, 기존 프레이즈 `references.json` 계약은 [발전 과정 안내](DEVELOPMENT_RECIPE.md)를 따릅니다. 국소 조성 참조는 프레이즈 자료에 추가되는 근거입니다.

## 설계의 선택 필드

`recipe.tonal_library_sha256`에는 `musigen.blueprint.digest(library)`를 넣습니다. 이는 정규화한 JSON 내용의 해시이며 파일 바이트의 SHA-256과 구별합니다. 각 stage의 `tonal_moves`에 다음과 같이 작성합니다.

```json
{
  "at_bar": 1,
  "offset": "0",
  "kind": "local_key_change",
  "reference_id": "beethoven-sonatas/01-2:local_key_change:58",
  "from_key": "G major",
  "to_key": "E minor",
  "observation": "원 주석에서 F장조에서 D단조로 국소 조성이 바뀐다.",
  "decision": "9마디부터 E단조에서 주제의 음가를 확대한다.",
  "pivot": {"bar": 8, "offset": "0", "from_figure": "I", "to_figure": "III"},
  "confirmation": {"bar": 12, "cadence": "PAC"}
}
```

위 예시는 9마디에서 시작하는 stage 안의 첫 마디입니다. `at_bar`는 **stage 안의 상대 마디**, pivot·confirmation의 `bar`는 **전체 곡의 절대 마디**입니다. offset은 4분음표 단위 분수입니다.

- 참조 ID·종류·장단조 쌍·철자를 포함한 이조 관계가 같아야 합니다. 관찰과 이번 곡의 결정을 각각 작성해야 합니다.
- 국소 조성 변화는 실제 앞 마디와 현재 마디의 조성이 맞아야 합니다. 현재 지원 범위는 2마디 이후의 마디 경계입니다.
- 으뜸화는 현재 조성을 유지하면서 해당 목적을 가진 실제 `secondary` 기능 화성이 있어야 합니다. 코드 심벌만 적고 세컨더리 기능을 주장할 수 없습니다.
- 선택한 공통화음은 앞 조성의 선행 마디에 있어야 하며 두 로마자 해석과 실제 화음의 구성음 철자·베이스가 모두 같아야 합니다.
- 종결 마디는 도착한 조성 구간 안에 있어야 하며 실제 상세 화성의 종지 **의도**와 일치해야 합니다. 독립적인 종지 판정은 추가하지 않습니다.

출력 `development_trace.json`에 원 주석·주변 문맥·원 파일 해시·작성 결정·실제 화성 대조가 남습니다. `tonal_references.json`과 한국어 `tonal_development.html`을 함께 저장하고 작품 목록에서 연결합니다.

## 2026-11-11 고정 표본 결과

| 작품/악장 | 결과 |
|---|---|
| Mozart K279-1 | 검증 통과 |
| Mozart K279-2 | 검증 통과 |
| Beethoven 01-1 | 원 악보와 주석 주소 불일치로 제외 |
| Beethoven 01-2 | 검증 통과 |
| Chopin BI105-2op30-2 | 원 악보와 주석 주소 불일치로 제외 |
| Chopin BI105-3op30-3 | 검증 통과 |

6개 중 4개, 주석 766행에서 **국소 조성 변화 10곳·명시적 슬래시 으뜸화 104곳**입니다. 이는 같은 작품 안의 사건 수이며 독립 작품 수나 정확도 통계가 아닙니다. 원 파일 검사 36회(공유 README/라이선스의 반복 검사 포함), 서로 다른 조성 관계 20개를 교차 확인했습니다.

실제 작성 시험은 기존 「햇살의 산책」을 사용했습니다. G장조–E단조–G장조 구간은 이전에도 있었으며 이번에 새 전조를 세 번 추가한 것이 아닙니다. 6마디의 A7→7마디 D7, 8마디 G 공통화음→9마디 E단조, 12마디 Em 공통화음→13마디 G장조를 각각 명시적 참조와 연결하고 11–12마디 종결을 수정했습니다. 선율 변화는 6·7·11·12마디, 왼손 변화는 6·11·12마디입니다. 첫 제시와 귀환의 모티프는 유지했습니다.

16마디·6/8·약 29초·페달 없음. 기존 musicomp 자료를 10마디에 적용하고 연결·종지의 직접 반주를 유지했습니다. 두 버전은 같은 선율을 사용하며 상세 화성 악보는 모든 구성음, 독주는 실제 배치와 생략음을 각각 기록합니다. 검사는 오류·경고 0개이며 사용자 청취 평가는 아직 없습니다.

- [조성 연결 근거](http://127.0.0.1:8802/tonal_development.html)
- [두 악보·피아노 음원·XML/PDF](http://127.0.0.1:8802/index.html)
- [수정 전 6/8 곡](http://127.0.0.1:8798/bright_68/index.html)

로컬 작업 트리 `K:/MusicGeneration/tonal-development`, 최종 라이브러리 `output/tonal-v005/library.json`, 최종 악보 `output/study-v003`. 폴더의 v번호는 내부 작성 반복이며 사용자 승인 버전 수가 아닙니다. 서버 재시작: `python -m http.server 8802 --bind 127.0.0.1 --directory output/study-v003`.

DCML의 CC BY-NC-SA 4.0 출처를 보존한 선택 관찰 기능입니다. `generation_eligible: false`를 유지하며 학습 자료 자동 투입, 작곡가 스타일 모델, P3/P4 중단 판정 변경은 없습니다. 다음 검증 범위는 원 XML 음표 시각의 독립 대조와, 새로운 모티프에서 조성 연결이 자연스러운지 실제 청취로 확인하는 일입니다.
