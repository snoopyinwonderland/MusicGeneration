# 41–50번 여러 마디 리듬·선율 결합 검수

브랜치 `codex/multibar-phrase-borrowing` · 기준 `a7f64c1`. 여러 마디에 걸친 구절의 일관성을 비교할 수 있게 2마디 출처 다섯 개와 3마디 출처 다섯 개를 4/4 피아노 단선율로 작성했다. 남은 한두 마디는 새 응답이다. [이전 선율 후보](http://127.0.0.1:8808/melody-phrases/round4.html) · [41–50번 듣기](http://127.0.0.1:8808/melody-phrases/round5.html)

편곡 프로젝트의 `musicomp/realize/retrieval.py`는 같은 출처의 다음 마디를 후보에 더하고 연속 선택 시 마디 경계의 전환 비용을 0으로 둔다. 이번에는 원칙을 주선율에 적용해 한 출처의 구절을 통째로 읽고, 서로 다른 작품의 리듬과 음높이 배열을 음의 순서대로 결합했다. 한 구절 안에서 리듬의 음 시작 시점과 음가, 쉼은 유지된다. 선율 출처는 필요한 경우 전체를 이조했다. 3마디 후보의 첫마디에 남아 있는 두세 박의 쉼도 리듬 출처의 시작 위치에 따른 것이다.

`musigen/rhythm_retrieval.py`의 `extract`에 선택 인자 `include_melody`를 추가했다. `musigen/phrase_borrowing.py`의 `rank_pairs`는 같은 길이와 음 개수에서 마디별 발음 수와 실제 시작·지속 시각을 비교한다. 같은 작품과 확인된 같은 곡 계열은 제외한다. `combine`은 마디 경계를 넘는 음을 붙임줄로 나누고, `build_study`에서 실제로 고른 출처를 `examples/multibar-phrase-borrowing.json`의 새 응답과 결합한다. 현재 작성에 사용한 자료는 Essen과 MTC-ANN이다.

MusicXML을 다시 읽어 40마디의 온셋·음가·음높이를 확인했다. 원자료 주석을 다시 읽은 독립 대조에서 모든 후보의 2–3마디 리듬과 이조 전후 선율이 출처 기록과 일치했다. 41번 앞 2마디는 7음, 46번 앞 3마디는 11음이며 주석 구절의 처음과 끝을 검증했다. 브라우저에서 모든 후보의 악보와 재생 시작, 전환과 정지를 확인했다.

재현 명령은 `python -m musigen.phrase_borrowing examples/multibar-phrase-borrowing.json --source-dir "K:/Music Composition/data/external/mtc" --out <새 출력 JSON>`이다. 생성한 악보와 감상 페이지는 로컬 8808과 `output/multibar-phrase-borrowing/`에서 확인할 수 있다. 출처 파일과 각 구절 번호는 감상 카드 및 레시피에 남겼다.

같은 레시피에서 검수한 악보 입력 JSON을 바이트 단위로 다시 만들었다. 별도 색인 대조의 두 마디 이상 연속 12음 일치와 16음 근접 일치는 791,135개 성부에서 0건이었다. 이 검사는 음정과 리듬을 함께 비교한다. 이번에 의도적으로 가져온 음정 배열이나 리듬은 각각 별도의 원자료 대조로 검증했다.

전체 테스트는 274개 중 273개 통과했다. 나머지 한 건은 앞선 작업에서 수정 전 코드로 재현된 「빛이 머무는 자리」의 프레이즈 경계 차이 `test_phrase_observations_have_real_breaths_and_all_notes`다.
