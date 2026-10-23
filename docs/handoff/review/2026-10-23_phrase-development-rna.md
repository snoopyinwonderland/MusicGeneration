# 프레이즈·주제 발전과 화성 표기 전환 검수 요청

- 브랜치: `codex/phrase-development-rna`, 기준 main `2c141fe`.
- musicomp는 병합된 main `c361a87`을 읽기만 사용. 분석·인식 계수 변경 없음.
- 구현, 단위 검사, 브라우저와 PDF 시각 검수 완료. 사용자 청취 승인 및 Claude 병합은 대기. main push 없음.

## 요청과 적용

사용자 원문: “음악 만들 때 프레이즈 분석 도구를 활용하면 좋겠는데요. 멜로디에 쉼표가 전혀 없고 주제가 뭔지 잘 드러나지 않습니다. 주제를 확장하는 구조로 만들면 좋겠고, 반주 패턴도 더 이용해 주세요.” 이어 현재 화성 기호와 Roman Numeral Analysis를 전환하는 버튼을 요청했다.

새 규칙이나 제목별 예외 없이 기존 주제 변형·반주 음형으로 「빛이 머무는 자리」를 고쳤다. `design.request`는 이번 실제 원문으로 고쳤고, 제목·조성·형식·구체적인 음은 작곡 제안으로 둔다. 기존 Claude 수정인 `duet --feedback`도 유지했다.

페달에 관한 마지막 선택은 “페달 표기 방식이 틀린 건 아니었네요. 그냥 둬도 되겠습니다.”, “더 잘 표시되는 방식을 쓰세요.”였다. 이 악보에서는 지속 길이와 해제 위치를 읽기 쉬운 기존 선 표기를 유지했다. Ped.–* 변경은 포함하지 않는다. 페달 교체 동작이나 기본 writer 변경도 없다.

## 바꾼 곳

| 파일·함수 | 역할 |
|---|---|
| `musigen/phrases.py`: melody, analyze | 오른손 첫 성부를 musicomp 모델로 옮겨 기존 동기·프레이즈 분석 호출. 실제 쉼과 설계 경계 비교. 선택 기능 |
| `musigen/checks.py`: check | `analysis.phrases`가 true일 때 결과 추가. 다성 선율 등은 이유와 함께 미평가 |
| `musigen/design.py`: validate | analysis와 phrase_plan 허용·형식 검증 |
| `musigen/harmony_labels.py`: analyze, label, display | music21 기반 기보 화음의 고전 로마자·전위 표시, 국소 조성과 실제 베이스 사용 |
| `musigen/listen.py`: _entry | 화성 표시 데이터 추가 |
| `musigen/listen_template.html`: applyHarmonyLabels, about | 코드 심벌/RNA 전환, 근거 표, 프레이즈 구간 재생. 화면 전환 중 음표·재생 시간 보존 |
| `examples/pieces/lingering_light` | 주제와 호흡을 중심으로 악보·설계 수정 |
| `tests/test_phrase_harmony.py`, `scripts/check_listen.cjs` | 분석과 화면 동작 검증 |
| `docs/listen/`, README, COMPOSING | 검수용 페이지와 자작곡 PDF, 사용법 |

프레이즈 분석은 `analyze_motifs(cross_check=False)` → `segment_layers`를 그대로 사용한다. 화성 추론을 호출하거나 계수를 조정하지 않는다. phrase_plan은 작곡 의도이며 자동 관찰과 구별한다. 새 분석 기본값은 꺼짐, 이번 곡에서만 명시적으로 켰다. RNA는 사용자가 버튼을 누르면 보이며 초기 화면은 기존 코드 심벌이다.

RNA는 music21 `romanNumeralFromChord`를 쓰되, 주어진 화음의 성질과 전위는 고전 표기법으로 정리한다. 단조 V7의 `V75#3` 같은 엔진 원문도 `engine_figure`에 보존한다. D6의 첨가6음과 D/F#의 제1전위를 혼동하지 않는다. 온음계 I→IV를 곧바로 V/IV로 부르지 않고, 반음계 근거와 다음 화음 해결을 함께 본다. 이것은 고정된 화음을 표시하는 기능이며 원곡 화음 인식 개선 실험이 아니다.

근거: [music21 Roman API](https://music21.org/music21docs/moduleReference/moduleRoman.html), [Roman numeral tutorial](https://music21.org/music21docs/usersGuide/usersGuide_23_romanNumerals.html). 페달의 선/기호는 [MusicXML pedal](https://www.w3.org/2021/06/musicxml40/musicxml-reference/elements/pedal/)의 별도 속성이다.

## 전후와 들어 볼 곳

로컬 기준: `output/virtual-composer-release/`.

| 항목 | 이전 | 이번 |
|---|---|---|
| 피아노 솔로 | lingering_light/v001 | lingering_light/v002 |
| 파생 듀엣 | lingering_light_duet/v002 | lingering_light_duet/v003 (솔로 v002에서 파생) |
| 주선율 실제 쉼 | 0곳 | 9곳, 총 7.5개 4분음표 길이 |
| 브라우저 재생 음 수 | 223 | 201 (듀엣: 바이올린 68 + 피아노 133) |
| 길이·조성·박자 | 60초, D장조, 3/4 | 유지 |
| 자동 프레이즈와 계획 | 분석 선택 안 함 | [1–4, 5–8, 9–12, 13–16, 17–20, 21–24], 계획 끝 6/6 일치 |

- 1–8: a의 ‘4분–8분–8분–4분’과 b의 하행 응답. 2·4·6·8마디 쉼으로 호흡. 왈츠형→분산화음.
- 9–12: a를 B–C#–D 시작음으로 상행 반복, 11마디 G5 절정, 12마디 쉼.
- 13–16: a의 음가 두 배 확대와 안쪽 응답. 베이스 중심→분산화음, 16마디 쉼.
- 17–20: a–b 재현, 알베르티 반주와 20마디 종지형.
- 21–24: 주제 단편과 셸 보이싱으로 마무리, 23마디 쉼. 프레이즈 끝 4·8·12·16·20·23은 마지막 박에 페달도 뗀다.

버전 기록상 오른손 변경은 1–23, 왼손은 1–5와 7–24마디다. 선율·화성 전체를 다시 설계한 수정이며 일부 마디 보존이라고 주장하지 않는다. 솔로→듀엣의 음높이·길이·이음줄·아티큘레이션 보존은 테스트한다.

최신 곡 주소는 `docs/listen/lingering_light/index.html`, `lingering_light_duet/index.html`. 고정판은 각각 v002.html, v003.html. 과거 공개 v001/v002는 남겨 전후를 열어 들을 수 있다. 여러 버전 비교는 output 폴더의 listen.html 사용. 공개 통합 최신 페이지는 부모를 포함하지 않는다.

## 확인

- Python 61→68개 모두 통과. 새 7개: 전위·첨가음, 부속화음·단조·차용화음, 실제 베이스·국소 조성, 실제 쉼·구간, 선택 기능·제목 독립, 여린내기·다성 거부, 계획 검증.
- 기존 after_rain MusicXML 바이트 회귀 포함, Node 재생 4개 통과.
- Chrome 6곡: Verovio 로그와 JS 오류 없음. RNA의 모든 화면 값이 계산 결과와 일치, 코드 심벌 복귀, 재생 중 전환해도 음 ID·음높이·시간 불변. 390px 화면 가로 넘침 없음.
- 새 솔로·듀엣의 XML/PDF/WAV 실제 받기 버튼 동작. XML 원본 일치, PDF 헤더 정상. WAV peak 0.2917/0.2134, RMS 0.0419/0.0371, 클리핑 없음. 바이올린 음소거와 프레이즈 9–12 재생(20–30초) 확인.
- PDF: 솔로 1쪽, 듀엣 2쪽. 전 페이지를 PNG로 렌더해 쉼표·주제 주석·페달선·여백 확인.
- `output/virtual-composer-release/browser-check.json`, solo-rna.png, duet-rna.png, duet-mobile.png, pdf-review/phrase-*.png에 검증 자료. output은 Git에 넣지 않는다.

## 범위와 위험

- 여섯 경계 일치는 자작 예시 한 곡의 결과다. 일반적 정확도나 청취상 주제 인식률이 아니다. 이번에는 실험용 계수·임계값을 새로 두지 않았다.
- 프레이즈 분석은 오른손 첫 성부 단선율만 지원한다. 분석 결과를 보고 작곡자가 수정했으며, 자동 재작곡 시스템은 아니다.
- 로마자 전환은 화면 전용. XML/PDF는 원본 코드 심벌이며 화면에도 명시했다. 프레이즈 구간의 국소 화성만 표시하고 구조적 화성 환원이나 비화성음 분석 전부를 주장하지 않는다.
- RNA는 Verovio가 그린 화성 그룹과 데이터 개수가 일치할 때만 켜진다. 더 복잡한 화성/반복/다면 기보는 별도 확인 필요. 현재 6곡은 모두 확인했다.
- musicomp와 MusicAnalysis 코드는 바꾸지 않았다. 음원·페달 재생의 기존 근사 한계와 듀엣 활 배분 미검수는 유지. MuseScore GUI·실연·사용자 청취 승인 미확인.

## 검수

Claude 검수 대기. main 병합 후 GitHub Pages에서도 솔로·듀엣 최신 버전 및 버튼을 확인해 주세요.
