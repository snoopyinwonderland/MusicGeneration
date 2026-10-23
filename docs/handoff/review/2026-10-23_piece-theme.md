# P2 주제 발전 검수 요청

브랜치 `codex/piece-theme`, P1 `4974197` 위에 쌓았습니다. musicomp `codex/xml-expression`을 먼저 병합해야 합니다.

## 변경과 검증
- `motif.apply`: delay/extend/tail. `piece._material`: 규칙적·불규칙적 seq와 반음 이동, 횟수·길이 검증.
- `theme_metrics.measure/score_window`, `checks.check`, 듣기 페이지: 성부별 음정·리듬 유사도, 출처/숨은 등장/구간별 마디 수.
- 두 예시의 9–11마디를 seq로 표현. 겨울 아침 왼손이 주제를 받고 오른손은 긴 음으로 응답합니다.
- 테스트 35→42개 통과. after_rain MusicXML 기준 파일과 바이트 동일, 펼쳐 쓴 9–11마디와 seq의 음·길이 동일.
- 실행: `python -m unittest discover -s tests` (`MUSICOMP_ROOT=K:\Music Composition-xml-expression`).

## 분포 (전체 성부의 모든 이동 창이 분모)
가중치 0.6/0.4, 임계 0.5/0.75/0.85는 명세의 잠정값입니다. 청취 인식률이 아닙니다.

| 곡/동기 | 전체 창 | <.5 | .5–.75 | .75–.85 | ≥.85 |
|---|---:|---:|---:|---:|---:|
| after_rain / a | 205 | 84 | 90 | 21 | 10 |
| after_rain / b | 205 | 160 | 29 | 5 | 11 |
| winter_morning / a | 196 | 73 | 112 | 1 | 10 |
| winter_morning / b | 198 | 95 | 79 | 15 | 9 |

## 들어 볼 곳
`output/p2/<곡>/v001`, `docs/listen/index.html` (두 곡 최신 버전).
겨울 아침 9–11마디 왼손 반복 진행, 12마디 응답. 낮은 점수 순 등장(0.5 미만이라는 뜻은 아님):
- after_rain 6마디 rh, 동기 b: 0.8667 (b|durs)
- after_rain 22마디 rh, 동기 b: 0.9333 (b|durs)
- after_rain 1마디 rh, 동기 a: 1.0000 (a)
- after_rain 3마디 rh, 동기 a: 1.0000 (a|at:D5)
- winter_morning 1마디 rh, 동기 a: 1.0000 (a)
- winter_morning 3마디 rh, 동기 a: 1.0000 (a)
- winter_morning 5마디 rh, 동기 a: 1.0000 (a)
- winter_morning 13마디 rh, 동기 a: 1.0000 (a|at:C5)

## 위험
동기 일부만 남은 출처는 전체 길이 점수를 내지 않습니다. 창은 구간 경계를 넘을 수 있으므로 점수 기준 마디 수는 출처보다 넓을 수 있습니다. 청취 판정과 임계치 채택은 미완료입니다. MuseScore 미확인. XML 회귀는 소리의 예술적 평가를 대신하지 않습니다.

## 검수
Claude 검수 대기.
