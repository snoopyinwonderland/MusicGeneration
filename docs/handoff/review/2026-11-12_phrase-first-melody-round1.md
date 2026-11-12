# 피아노 단선율 1차 청취 검수 요청

- 브랜치 `codex/phrase-first-melody-round1` · 기준 `4fb84dc` · 작업 트리 `K:/MusicGeneration/melody-research`
- 이전 비교 대상은 [막차 전 한 잔](http://127.0.0.1:8808/last-train-jazz.html) 최신 청취판이다. 사용자는 17–19마디의 연결은 조금 괜찮고 나머지는 같은 상행·하행 패턴이 이어진다고 했다. 그 세 마디에서 쉼 뒤에 움직이기 시작해 높은 음에 머물고, 다음 마디에서 음값을 다시 압축하는 전환을 관찰했다.
- 모티프의 인상과 프레이즈의 속도 변화를 비교할 수 있도록 세 후보를 반주와 페달 없이 작곡했다. 통계에서 관찰한 리듬 변형과 긴 끝음을 활용했다. 기존 곡의 선율이나 패턴 조각은 가져오지 않았다.

## 청취할 악보

[세 후보 비교 및 MusicXML·PDF](http://127.0.0.1:8808/phrase-first-round1.html). 각 페이지의 프레이즈 버튼으로 해당 구간을 들을 수 있다.

| 후보 | 형식 | 들어 볼 마디 |
| --- | --- | --- |
| [창가에 남은 말](http://127.0.0.1:8808/listen/phrase-first/v001/window_words.html) | D장조 · 4/4 · 16마디 | 1마디의 반복음과 9마디의 변형, 12마디의 높은 끝음, 15–16마디의 귀환 |
| [한 걸음 늦게](http://127.0.0.1:8808/listen/phrase-first/v001/one_step_late.html) | G단조 · 3/4 · 20마디 | 1마디의 엇박 도약과 쉼, 9–13마디의 음역 전환, 17–20마디의 바뀐 응답 |
| [비가 걷히는 동안](http://127.0.0.1:8808/listen/phrase-first/v001/after_rain_clears.html) | A♭장조 · 4/4 · 16마디 | 2–3마디에 걸친 붙임줄, 12마디의 쉼과 13마디의 최고음, 15–16마디의 마무리 |

## 자료 관찰

- 새 선택 실행 도구 `musigen/phrase_corpus_observe.py`의 `indexed` 및 `observe_batch`는 두 선율 DB의 모든 인덱스 행을 읽는다. 전체 선율 지문으로 중복을 제외한 성부 791,085개와 음 시작 165,364,377개를 계산했다. 역할 근거가 있는 성부 273,423개와 역할 미확정 성부 517,662개를 구분했다. 기보 4분음표 단위와 연주 초 단위를 출처별로 구별했다.
- 다음 음까지의 무음이 성부 중간 음값의 0.75배 이상이면서 0.5박 또는 0.12초 이상인 경우, 또는 성부 중간 음값의 2.5배 이상인 긴 음에 3반음 이상 이동이 뒤따르는 경우를 경계 후보로 삼았다. `observe`는 4–32음 구간의 반복음·도약·방향 전환·긴 끝음과 첫 4음의 음정·시작 간격을 집계한다. 시작 간격은 그 합계에 대해 24칸으로 정규화한다.
- 역할 근거가 있는 성부의 4–32음 구간은 2,893,150개였다. 첫 구간 이후 비교 2,692,621회 중 580,506회에서 첫 4음의 리듬이 같은 칸에 들어가고 음정 배열이 달랐다. 긴 음을 경계 추정에 이미 사용하므로 이 구간의 끝음 통계에는 선택 효과가 있다.
- `mtc_annotations`는 MTC-ANN의 `phrase_end`와 `IOI_frac`로 360곡의 표시된 프레이즈 1,890개를 읽는다. 1,534/1,890개는 끝음이 앞 음들의 중간 음값보다 1.5배 이상 길었다. 첫 프레이즈와 비교한 후속 프레이즈 1,530개 중 510개는 첫 4음에서 비슷한 시작 간격과 다른 음정 배열을 사용했고, 118개는 리듬과 음정이 모두 일치했다. 반복음이 있는 프레이즈는 1,348/1,890개였다.
- 첫 4음의 유사성은 청취자의 모티프 인지를 직접 측정하지 않는다. 위 수치는 각 자료와 경계 방법에 해당한다. 기존 DB에서 파싱에 실패한 파일과 인덱싱되지 않은 자료는 집계 범위 밖이다.

## 중복과 검증

- 기존 생성 작업 폴더에서 정규 악보 경로 304개를 읽어 첫 보표의 첫 성부를 추출했다. 이전 결과 DB와 합쳐 지문이 서로 다른 선율 50개를 확인했다.
- 기존 `musigen.melody_line_audit`로 두 자료 DB와 이전 출력 DB를 대조했다. 총 791,135개 중복 제거 성부에서 후보별 2마디 이상에 걸친 연속 12음의 음정·리듬 일치와 연속 16음의 근접 일치가 모두 0건이었다. 전체 이조와 균일한 빠르기 변화를 허용했다. 16음 근접 기준은 음높이 최대 1개 차이와 상대 리듬 오차 12% 이하다.
- 이전 생성 선율 50개 및 이번 후보끼리의 연속 8음 일치도 모두 0건이었다. 이 비교는 이조·속도 보정 뒤 음높이 차이, 시작 시점과 음값이 모두 같은 구간에 해당한다. 이들 검사로 짧은 음형이나 검사 범위 바깥의 유사성을 판정할 수는 없다.
- MusicXML을 다시 읽어 설계와 음높이·시점·길이를 대조했다. PDF 3개는 각 한 페이지로 출력해 시각 확인했다. 내장 브라우저에서 피아노 샘플로 재생 시작과 정지를 세 곡 모두 확인했다. MusicXML, PDF, 청취 페이지 및 공유 에셋 12개의 로컬 HTTP 응답을 파일과 대조했다.
- `python -m unittest discover -s tests` 266개 통과. 집계 도구는 선택 실행한다. 사용자의 선호는 후속 청취로 확인한다.

## 재실행과 로컬 산출물

기존 인덱스를 구축하는 절차는 [선율 근거 문서](../../MELODY_EVIDENCE.md)에 있다.

```powershell
$py = 'K:/Music Analysis/.venv/Scripts/python.exe'
$env:MUSICOMP_ROOT = 'K:/Music Composition'
$env:PYTHONUTF8 = '1'
& $py -m musigen.phrase_corpus_observe --database output/melody-data/melodies.sqlite3 --database output/annotated-data/melodies.sqlite3 --mtc 'K:/Music Composition/data/external/mtc/MTC-ANN-2.0.1_sequences-1.1.jsonl.gz' --out output/phrase-first-round1/phrase-observations.json --workers 8
& $py -m musigen.melody_line_audit --queries output/phrase-first-round1/queries.json --database output/melody-data/melodies.sqlite3 --database output/annotated-data/melodies.sqlite3 --database output/previous-data/melodies.sqlite3 --database output/phrase-first-round1/previous.sqlite3 --out output/phrase-first-round1/originality.json --workers 8
```

곡별 악보, 집계 JSON과 중복 검사 결과는 작업 트리의 Git 제외 `output/phrase-first-round1`에 있다. 청취 페이지는 같은 작업 트리의 `output/melody-studio`에서 포트 8808로 제공한다.
