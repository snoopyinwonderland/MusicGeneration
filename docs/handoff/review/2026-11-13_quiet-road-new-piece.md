# 「조용한 귀갓길」 피아노 솔로 검수 요청

브랜치 `codex/quiet-road-new-piece` · 기준 `71a4fd5`. 새 피아노곡을 요청받아 [조용한 귀갓길](http://127.0.0.1:8808/listen/quiet-road/v002/index.html#piece=quiet_road&version=v002)을 A단조, 4/4, ♩=84, 20마디로 작성했다. 약 57초다. 청취판에 피아노 재생, 구간 재생, MusicXML·PDF·WAV 받기가 있다.

## 구성과 출처

- 첫 마디의 약박 A–C–E는 5마디에서 A–C–F로 변형되고, 13마디의 높은 A 뒤 15마디에서 돌아온다. 4·8·14마디 끝에는 양손이 함께 쉰다.
- [이전 곡](http://127.0.0.1:8808/listen/lamp-in-the-window/cadence/index.html#piece=lamp_cadence&version=v001)과 같은 피아노 음원으로 새 곡의 9–14마디와 19–20마디를 들어 볼 수 있다. 19마디에서 낮은 E 위에 E7을 얹고, 20마디에서는 오른손과 저음 A를 네 박 유지한다. 왼손의 안쪽 화음이 한 박 뒤에 들어온다.
- 짧은 모티프 세 개를 이조해 오른손 69음 중 14음에 적용했다. 3–4마디는 「나는 반딧불」의 4음, 9–10마디는 That’s So True의 4음, 11–12마디는 My Love (And)의 6음이다. 9–10마디의 리듬은 「나는 반딧불」, 11–12마디의 리듬은 Pink Pony Club의 다른 구간을 사용했다. 각 모티프는 원래의 상대 음정을 유지하며 다른 리듬으로 재배치했다.
- 작업 파일은 Git 제외 `output/quiet-road`에 있다. `create.py`의 `main`은 `musigen.melodic_borrowing.fit_options`로 후보를 구하고 세 구간을 골라 양손 악보를 작성한다. `publish.py`는 `musigen.listen._write_page`로 청취판을 만들며 `report.json`은 원자료 위치와 사용 음수를 기록한다.

양손 122개 음 사건의 시점·길이·음높이·보표·성부를 MusicXML 재읽기와 대조했다. 악보 검사 오류·주의 0건이며, PDF 한 페이지와 브라우저 재생을 확인했다. 데이터베이스 791,135개 성부에서 연속 12음 일치·16음 근접 일치 0건이었다. 이 검사 범위는 기보 유사도다. 전체 테스트 273개 통과.
