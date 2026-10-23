# P1 기보 확장 검수 요청

상태: 구현·자동 검사·브라우저 동작 확인 완료. 사용자 청취 미평가, main 미병합.
브랜치: `codex/piece-notation`, 기준 `fb92af9`.
의존성: musicomp `codex/xml-expression`. Claude가 이 의존성을 먼저 검수·병합한 뒤 이 브랜치를 병합한다.
검증할 때는 `$env:MUSICOMP_ROOT='K:\Music Composition-xml-expression'`을 지정한다.
기존 musicomp main은 새 표기 없이 계속 사용할 수 있으나, 새 표기에는 의존성 브랜치가 필요하다.

## 변경과 근거

ROUND1 P1 명세에 따라 새 필드를 사용하는 경우에만 여린내기·표현 기호를 추가했다.
XML 후처리 없이 musicomp writer를 이용한다.

- `design.pickup/seconds`: 분수 길이·범위 검사, 전체 시간에 여린내기 추가.
- `notation.parse/Ev`, `motif.apply`: 아티큘레이션, 이음줄 짝 검사, retro/frag 끝점 보존.
- `piece.Piece/build/_place`: 0마디 좌표, 누락한 여린내기 쉼표, 붙임줄 병합의 이음줄 끝 보존.
- `expression.compile_expression/playback`: 페달·증감 구간 및 4분음표 단위 재생 데이터. 겹치는 지시 거절.
- `piano_io.write_musicxml`: 0마디와 원래 길이의 마지막 마디, 기호 출력. 인접 페달은 change로 연결.
- `versions.bar_signature`, `listen._entry`, `listen_template.html`: 0마디 비교, Verovio qstamp 시간 변환, 셈여림·페달·주법 재생.
- `examples/pieces/winter_morning`: 가상 요청에 대한 자작곡. 6/8, 여린내기 1/2, G장조, 44, 6급, 65.91초.

## 검증

- 기존 24 → 전체 35 테스트 통과.
- `tests/data/after_rain_v001.musicxml`: 수정 전 writer로 캡처. 새 필드 없는 비 갠 밤 출력 바이트 동일.
- 새 문법 정상/오류, 여린내기 번호·implicit, copy 0 거절, retro/frag, 붙임줄 병합, 페달 start/change/stop 검사.
- 두 곡 music21 읽기 및 MIDI 생성 성공(forceSource=True).
- Verovio 6.3.0-425dd7b: 두 곡 load/render/timemap 및 브라우저의 `getLog()` 빈 문자열.
- Chrome headless: 두 곡 악보 표시, 재생/일시정지/정지, 런타임 오류 0. 겨울 아침 0마디와 24온마디 확인.
- 최초 예시의 과도한 block 보이싱과 인접 페달 경고를 수정했다. 최종 예시 기존 검사 errors/warnings 0.
- MuseScore 4는 확인 가능한 설치 위치에서 발견하지 못해 확인 못 함.

## 들어 볼 곳

`K:\Music Generation-codex\docs\listen\index.html` (두 곡, 아직 GitHub Pages main 배포 아님).
생성 결과: `output/p1/after_rain/v001`, `output/p1/winter_morning/v002`.
겨울 아침: 0마디 여린내기·테누토, 1–3 증감, 1–8 마디별 페달, 9–11 왼손 주제와 오른손 긴 음,
9–13 고조, 14–16 이완, 21–24 약해짐, 24마디 유지 페달.

## 위험과 한계

음량 배수(pp .35, p .5, mp .65, mf .8, f .95, ff 1.1), 주법 배수는 명세의 잠정값이다.
실제 피아노 샘플이나 음향 측정이 아니다. 브라우저의 페달은 합성음의 감쇠를 유지하며 해제 시점만 연장한다.
기보 이음줄은 재생 프레이징 모델이 아니다. 곡 중간 박자/조표 변경은 범위 밖.
청취 품질과 정서 반영은 미평가다. 예시의 변경은 자작곡의 작곡 선택이며 곡별 코드 분기는 없다.
