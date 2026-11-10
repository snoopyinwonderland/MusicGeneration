# 짧은 선율 → 곡의 선율과 상세 화성

첫 목표는 **주제를 발전시킨 단선율과 충분한 화성 정보**를 안정적으로 만드는 것입니다. 피아노 독주·앙상블의 연주 배치는 기존 musicomp에 맡깁니다. `blueprint`는 선택 명령이며 기존 `piece`·`compose` 결과를 바꾸지 않습니다.

현재 작곡자는 대화에서 발전 설계와 음을 작성합니다. 이 명령은 설계를 실현하고 검증·출력합니다. 모티프 하나만으로 완성곡을 자동 작곡하는 학습 모델이나 P2의 승인된 프레이즈 선택기를 구현한 것은 아닙니다.

## 사용

작업 폴더에 `motif.json`과 `development.json`을 둡니다. 처음 주제는 `input` 이름으로 자동 등록되며 음높이·철자·음가·쉼을 그대로 제시해야 합니다. 이후 구절에는 기존 모티프 변형 연산과 직접 작성한 음을 함께 씁니다.

```powershell
$env:MUSICOMP_ROOT = 'K:\Music Composition'
python -m musigen blueprint <작업 폴더> --out output\새결과
python -m musigen blueprint <작업 폴더> --out output\새결과2 --arrange
```

`--arrange`는 기존 musicomp의 지정 화음 모드와 검색 반주를 호출합니다. 현재 스타일은 `lyrical`, 급수는 설계의 `basics.grade`(생략 시 6)입니다. 다른 스타일의 자동 선택은 후속 작업입니다. 출력 폴더가 비어 있지 않으면 중단합니다.

결과:

- `melody_harmony.musicxml`: 단선율과 전체 화음 구성음을 담은 왼손 요약 악보. 코드 기호는 보표 아래에 둡니다.
- `harmony.json`: 아래 교환 정보와 출처를 담은 상세 화성 파일.
- `melody_harmony.mid`: MIDI 변환에 성공한 경우의 미리듣기 파일.
- `checks.json`, `result.json`: 음악 검사와 MusicXML 재읽기 결과. 경고는 청취 판단을 대신하지 않습니다.
- `index.html`, `melody_harmony.html`: 화성 표와 악보·피아노 샘플 재생·MusicXML/WAV 다운로드. HTTP 서버로 열어야 합니다.
- `arrangement/stage1_piano_solo.musicxml`, `piano_solo.html`: 편곡 옵션의 피아노 독주. musicomp 내부 실행은 다른 편성 파일도 만들지만 이 기능의 화면에는 두 버전만 제공합니다.

PDF 자동 렌더러는 이번 명령에 포함하지 않았습니다. 별도 렌더링한 `melody_harmony.pdf`, `piano_solo.pdf`가 출력 폴더에 있으면 `musigen.blueprint_pages.write_pages`를 다시 호출할 때 받기 버튼에 포함됩니다. 없으면 버튼을 비활성화합니다. 첫 청취 초안에는 실제 렌더링·시각 검사를 마친 PDF를 연결했습니다.

## 발전 설계

`development.json`의 형식:

```json
{
  "format": "musicanote-development",
  "version": 1,
  "design": {
    "title": "검증용 짧은 응답",
    "basics": {"key":"C", "mode":"major", "meter":"4/4", "tempo":90, "grade":6},
    "form": [{"label":"A", "bars":[1,2], "function":"statement"}],
    "phrase_plan": [{"bars":[1,2], "role":"제시와 응답", "plan":"주제 뒤에 하행 응답"}]
  },
  "score": {
    "blocks": [
      {"bars":"1", "rh":{"motif":"input"}},
      {"bars":"2", "rh":"D5/h C5/h"}
    ]
  },
  "harmony": [
    {"bar":1, "duration":"2", "symbol":"C/E", "function":"tonic"},
    {"bar":1, "offset":"2", "duration":"2", "symbol":"Am7"},
    {"bar":2, "duration":"2", "symbol":"G7/B", "function":"dominant"},
    {"bar":2, "offset":"2", "duration":"2", "symbol":"C", "cadence":"IAC"}
  ],
  "references": []
}
```

이 예시에 맞는 `motif.json`은 다음과 같습니다.

```json
{"format":"musicanote-motif","version":1,"events":[
  {"duration":"1","pitches":[]},
  {"duration":"3","pitches":["E5"]}
]}
```

`design`·`score`의 기존 작성 문법은 [COMPOSING.md](COMPOSING.md)를 따릅니다. `score`에는 오른손 1성부 단선율만 쓰며 왼손·코드·페달은 중복 기입하지 않습니다. 기능·종지 라벨은 작곡 의도입니다. 자동 분석의 정답이나 사용자 승인으로 취급하지 않습니다.

## 상세 화성 교환

시간은 전부 **4분음표 길이**입니다. 마디는 1부터, `offset`은 0부터 셉니다. `"1/2"` 같은 분수를 사용합니다. 이벤트는 한 마디 안에 있어야 하며 모든 마디를 빈틈과 겹침 없이 덮어야 합니다. 같은 화음도 다시 지정하면 별도 이벤트로 보존합니다.

| 정보 | 의미 |
|---|---|
| bar, offset, onset, duration | 마디·마디 내 시점·곡 전체 시점·정확한 길이 |
| symbol, root, quality, tones | 코드 기호·근음·종류·철자를 보존한 전체 구성음 |
| bass, inversion | 지정 베이스·기본위치 0/전위 1–3. 첨가음·비화성 베이스에는 전위 숫자를 억지로 부여하지 않음 |
| voicing | 옥타브까지 지정한 왼손 배치. 생략하면 한 옥타브 안의 밀집 배치 생성 |
| key, roman | 조성과 로마자 표시. 첨가6음과 제1전위를 구분 |
| function | 선택적 tonic/predominant/dominant/other 의도 |
| cadence, cadence_status | PAC/IAC/HC/DC/PC/EC 의도. 검증되지 않은 작곡자 라벨임을 명시 |
| melody_relation | 해당 화음 위에 실제로 울리는 선율음·화성음 여부·앞 이벤트에서 이어진 음 여부 |
| note, source, references | 판단 근거와 출처. 기본은 작곡자가 제안한 자료로 기록 |
| phrase_plan, motif_sha256, plan_sha256 | 구절 설계와 입력 파일 식별 |

왼손에는 생략 없는 전체 구성음과 지정 베이스가 있어야 합니다. 선율의 비화성음을 임의로 화성음으로 옮기지 않습니다. 각 비화성음의 경과음·전타음·해결 방식은 이 단계에서 확정하지 않습니다.

지원 코드: 장·단3화음, 7/maj7/m7/m7b5/dim/dim7/aug/sus2/sus4/7sus4/6/m6/add9/madd9 및 슬래시 베이스. 지원하지 않는 9·11·13화음 등을 조용히 단순화하지 않습니다. 단일 박자·온마디 시작으로 한정합니다.

2026-11-10 후속 확장: `figure`에 `V7/V`, `V65/ii`, `viio7/ii`, `iv`, `N6`, `It6`, `Fr43`, `Ger65` 등을 명시할 수 있습니다. `symbol`을 함께 쓰면 구성음·베이스가 일치해야 합니다. 증6화음은 `figure`만 씁니다. It6/Fr43/Ger65는 MusicXML의 Italian/French/German으로 내보내며 F#을 Gb로 바꾸지 않습니다. 증6화음의 `root`는 null이고 XML root는 기능 기준 으뜸음입니다. `functional_intent`에는 목표 조성·근음·경향음을, `resolution_check`에는 다음 화음의 목표 도착 여부와 증6화음 두 경향음의 옥타브를 고려한 반음 해결 여부를 기록합니다. 전체 성부 연결이나 종지를 검증했다는 뜻은 아닙니다.

`score.blocks[].key`에 `G major`처럼 국소 조성을 지정하면 해당 블록에 적용하며, 키를 생략한 다음 블록은 곡의 기본 조성으로 돌아갑니다. 첫 블록은 기본 조성과 같아야 합니다. 실제 조표·장단조를 XML로 쓰고 다시 읽어 확인합니다. 단순한 부속화음 사용과 전조 선언을 구별하며, 작곡자가 선언한 조성이 음악적으로 확립됐는지는 별도 청취·종지 검토 대상입니다.

**편곡 전달 범위:** musicomp는 MusicXML의 선율, 화음 시점, 구성음, 베이스를 읽습니다. 별도 JSON의 기능·종지 의도·정서·출처·보이싱 의도는 아직 읽지 않습니다. 독주 편곡에서 요약 악보의 배치를 그대로 유지한다는 보장도 없습니다. 화성 기호와 로마자 전환은 화성 악보에서 제공하며, 화성 기호가 없는 musicomp 독주 출력에서는 로마자 버튼을 비활성화합니다. 독주 페이지 표현 재생은 현재 기본값이며 편곡 XML의 세부 표현을 모두 재현하지 않습니다.

입력 화면·작곡가 참조와 다음 개발 단계는 [MOTIF_STUDIO.md](MOTIF_STUDIO.md)를 보세요.

## 데이터 활용의 다음 순서

1. 이번 꾸러미: 위 교환 형식과 정확한 전달, 첫 두 악보 비교. 기존 피아노 반주 라이브러리만 활용합니다.
2. 다음 꾸러미: 사용 가능한 데이터의 권한·출처를 확인하고 사람이 검수한 구절 표본을 만듭니다. 선율 윤곽, 리듬, 쉼, 반복·변형 관계, 화성 리듬, 베이스와 종지를 구절 단위로 연결합니다. 기존 자동 화성 분석의 실패한 품질 관문을 우회하지 않습니다.
3. 그다음: 프롬프트와 모티프에 맞는 발전 사례를 검색하고 구절 계획 후보에 근거를 표시합니다. 같은 모티프·화성·템포로 데이터 사용 전후를 비교 청취합니다.

클래식 제목은 장면·장르의 약한 단서로, 가사는 문장·정서 변화의 단서로 취급합니다. 제목 또는 가사의 정서와 실제로 들리는 음악의 정서를 동일시하지 않습니다. 가사와 음표의 정렬 신뢰도, 수동 검수 여부, 라이선스를 별도로 남기고 원곡 선율을 통째로 재사용하는 검색은 하지 않습니다. KYSing·AI Hub 자료는 권한 확인 전 사용하지 않으며 DCML도 선택 옵션으로 둡니다.
