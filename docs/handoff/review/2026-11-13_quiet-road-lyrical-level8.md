# 「조용한 귀갓길」 Lyrical Level 8 편곡 검수

브랜치 `codex/quiet-road-lyrical-level8` · 기준 `404beed`. 사용자는 마지막 작곡을 Lyrical · Level 8로 편곡한 결과를 요청했다. [피아노 비교판](http://127.0.0.1:8808/listen/quiet-road/lyrical-level8/index.html#piece=quiet_road_lyrical&version=v002)에서 두 판을 선택하거나 **9–12마디 전후 듣기**로 이어서 들을 수 있다. 8808 작품 목록의 「조용한 귀갓길」에도 링크가 있다.

- `output/quiet-road-lyrical/engine.py`는 기존 `musigen.corpus_accomp.semantic`을 사용해 선율·지정 화성·프레이즈를 넘기고, `musicomp.stages.build_stages`를 `piano_mode=retrieval`, `style_plan=[{"from_bar":1,"style":"lyrical"}]`, `grade=8`, `fills=False`, `pacing=True`, `seed=0`, `piano_only=True`로 실행한다. 6곡의 반주 자료를 검색해 사용했다.
- `render.py`는 엔진의 왼손을 적용하고 69개 오른손 음의 시점·음높이·길이와 이음줄을 유지한다. 지정 화성, 빠르기, 악구의 표현을 기존판과 대조했다. 왼손 음 사건은 53개에서 72개가 됐다. 1·15마디는 A 옥타브와 펼침화음이 나오고, 9–12마디는 왼손 움직임이 늘었다.
- 편곡 후 4·8·14마디에서 양손이 쉬도록 엔진의 마디 끝 음을 덜어냈다. 10마디의 21반음 벌림은 E를 한 옥타브 내려 다듬었다. 16마디의 지속음을 별도 성부로 기보하고, 18마디의 병행 8도는 왼손 보이싱을 조정했다. 19마디 저음 E와 20마디 A 옥타브는 각각 네 박 유지한다. 엔진의 생출력과 보정 기록은 `engine.musicxml`, `engine.json`, `report.json`에 있다.
- `publish.py`는 기존 재생기를 사용해 전후 비교 및 MusicXML·PDF·피아노 WAV 버튼을 제공한다. 작업 파일과 악보는 Git 제외 `output/quiet-road-lyrical`에 있다. 두 판은 같은 피아노 샘플을 사용한다.

Level 8 프로필의 악보 검사 오류와 주의는 0건이었다. MusicXML 재읽기의 양손 음 이벤트를 대조했고 PDF 한 페이지를 확인했다. 브라우저에서 9–12마디 기존판→편곡판 전환을 확인했다. 전체 테스트 274개가 통과했다. Level 8은 엔진 설정이며, 음색과 난이도에 대한 청취 평가는 별도로 남는다.
