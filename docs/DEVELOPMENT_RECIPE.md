# 모티프 발전 과정 작성과 두 악보 출력

`python -m musigen.development_recipe`는 사람이 작성한 구간별 발전 설계를 기존 작곡·피아노 실현 경로에 전달하는 선택 명령입니다. 모티프만으로 음높이와 화성을 결정하는 학습 모델은 아닙니다. 첫 제시를 정확히 보존하고 자료 관찰, 작곡 판단, 실제 출력의 관계를 기록합니다.

입력 폴더에는 `motif.json`, `recipe.json`, `references.json`이 필요합니다. 참조 자료는 [프레이즈 참조 명령](PHRASE_REFERENCE_LIBRARY.md)으로 만든 관찰 결과입니다. 원자료의 라이선스와 범위를 유지하세요.

```powershell
$env:MUSICOMP_ROOT = 'K:\Music Composition'
python -m musigen.development_recipe --work output/my-input --out output/my-piece --corpus-accompaniment
```

출력 폴더는 새 폴더여야 합니다. 반주 자료 옵션을 생략하면 작성한 반주만 사용합니다. 검증된 PDF를 출력 폴더의 `melody_harmony.pdf`, `piano_solo.pdf`에 준비한 뒤 같은 입력으로 `--pages-only`를 실행하면 다운로드 버튼이 연결됩니다. 이때 저장된 `solo_score.json`을 사용하며 반주를 다시 검색하지 않습니다. 이 명령 자체는 PDF 생성기가 아닙니다.

## 입력 계약

`recipe.json`의 형식은 `musicanote-development-recipe`, version은 1입니다.

| 필드 | 내용 |
| --- | --- |
| `design` | 제목, 조성·박자·빠르기, 주제, 정서, 분석 옵션 등 기존 설계. `form`과 `phrase_plan`은 stages에서 작성 |
| `stages` | 순서대로 연결되는 구간 목록 |
| `harmony` | 전체 곡의 절대 마디 기준 상세 화성. 기존 blueprint 계약 사용 |
| `expression` | 선택적 셈여림·페달 등 기존 표현 구간 |
| `request` | 실제 요청 원문. 선택·청취 승인으로 해석하지 않음 |

각 stage에는 양의 정수 `length`, `role`, `label`, `reference_ids`, `observation`, `decision`, `blocks`가 필요합니다. role은 statement, response, development, contrast, return, cadence 중 하나입니다. 선택 필드 `cadence`는 계획의 종지 의도입니다. 판정된 종지라는 뜻은 아닙니다.

blocks의 `bars`는 해당 구간 안의 1부터 시작하는 상대 마디입니다. 빈틈과 겹침 없이 구간 끝까지 이어져야 합니다. `copy`도 구간 안의 앞 마디만 참조하며 컴파일 때 절대 마디로 옮깁니다. 기존 `motif`, `pitches`, `ops`, `seq`, 직접 음표, 반주 패턴 문법을 씁니다. 모든 블록에 `lh`가 필요하며, 자료 검색을 하더라도 직접 작성한 종지 반주는 유지할 수 있습니다.

`reference_ids`는 status가 observed인 프레이즈만 가리킵니다. `observation`에는 실제로 관찰한 끝 쉼·끝 음가·관계 등을, `decision`에는 그 관찰을 어떻게 해석하여 이번 곡에 적용했는지를 씁니다. 관련된 악구라는 주석을 동일한 음열이라는 증거로 바꾸거나, 직접 선택한 확대·조각 기법을 자동 학습 결과라고 기록하지 마세요.

## 출력과 보존

- 두 버전의 MusicXML·감상 HTML: 멜로디 + 상세 화성, 피아노 솔로.
- `harmony.json`: 전체 구성음, 베이스, 전위, 국소 조성, 로마자, 길이, 종지·기능 의도.
- `performed_harmony.json`: 실제 왼손 음표·출처와 설계 화음에서 생략된 음. 펼쳐진 음들을 동시 화음으로 오해하지 않도록 범위도 기록.
- `development_trace.json`: 입력 해시, 구간 역할, 관찰/판단, 실제 발음 수·쉼 길이·음역·재료 출처.
- `solo_score.json`, 선택 시 `accompaniment_report.json`: 반주 선택의 고정 결과와 자료 출처.

첫 제시의 음높이·음가·쉼, 두 버전의 선율, 상세 화성·국소 조성의 교환은 기존 검증을 통과해야 합니다. 쉼 통계는 단선율 RH를 대상으로 합니다. phrase_plan은 설계이고 자동 분석 결과와 별개입니다. 청취 품질이나 연주 가능성을 숫자만으로 확정하지 않습니다.

## 2026-11-11 재사용 시험

작업 트리 `K:\MusicGeneration\motif-transfer`, 입력 `output/study-input`, 최종 출력 `output/studies-v002`. 두 모티프는 이 시험을 위해 새로 작성했으며 사용자 선택으로 기록하지 않았습니다.

| 곡 | 기본 설계 | 발전 |
| --- | --- | --- |
| 고요한 창가 | D단조, 3/4, ♩=76, 16마디 | 네 음 주제 → 응답 → F장조 구절의 음가 확대 → 귀환 |
| 햇살의 산책 | G장조, 6/8, 점4분음표=66, 16마디 | 쉼 뒤 세 음 주제 → 조각과 응답 → E단조 확대 → 귀환 |

두 곡은 1–4, 5–8, 9–12, 13–16마디의 네 구간을 사용했습니다. 각 곡 12마디에 기존 musicomp 반주 자료를 적용했고 4·8·12·16마디 직접 반주는 보존했습니다. 페달은 없습니다. 첫 모티프와 상세 화성 교환은 검증되었지만 낯선 모든 모티프에 대한 자동 작곡이나 품질 일반화를 증명한 시험은 아닙니다.

전체 테스트 148개 통과. 두 독주 악보 오류·경고 0개. 3/4 상세 화성 요약 악보에는 15→16마디 병행8도 경고 1개가 남습니다. 실제 독주 반주와 구별한 전 구성음 요약 배치이며 경고를 숨기거나 검사 계수를 바꾸지 않았습니다. 6/8 자동 프레이즈는 대조부를 계획한 9–12 대신 10–12마디로 보고합니다. 이 차이도 보존합니다.

감상: <http://127.0.0.1:8798/index.html>. 서버 재시작은 작업 트리에서 `python -m http.server 8798 --bind 127.0.0.1 --directory output/studies-v002`입니다. 모차르트 스타일 생성은 별도 보류 상태입니다.
