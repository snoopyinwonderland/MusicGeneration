# P4 수정 흐름 검수 요청

브랜치 `codex/piece-revision`, P3 `f5da065` 위에 쌓았습니다.

## 변경
- CLI `--feedback`, `--interpretation`; `versions.save/_history`가 원문과 해석을 구분하고 feedback 누락 때 reason을 사용합니다.
- `versions.joins/join_notes`: 연속 변경 범위와 앞뒤 연결부, 음계상 6도 초과 도약을 참고로 기록합니다.
- 마디 비교는 음높이·길이뿐 아니라 성부, 아티큘레이션·이음줄·셈여림·표현 지시도 포함합니다. 과거 부모 버전은 저장된 입력으로 비교값을 다시 만들어 형식 변경에 의한 가짜 차이를 피합니다.
- 듣기 페이지: 부모→현재 순으로 연결부까지 재생, 범위 사이 1초 휴식, MEI measure@n으로 변경 마디 배경 강조. 수동 재생·정지·곡 선택은 비교를 종료합니다.

## 검증과 재현
49→52개 테스트 통과. 피드백·이력·보존·연결부·표현만 바뀐 마디 검증. after_rain 기준 XML 바이트 동일.
모든 수정 시연 입력과 버전은 `output/p4`에만 두었습니다. 공개 docs/listen에는 수정 시연을 포함하지 않았습니다.

```powershell
python -m musigen piece "K:\Music Generation-codex\examples\pieces\after_rain" --out "K:\Music Generation-codex\output\p4\after_rain" --feedback "기준 초안" --interpretation "P3와 같은 자작곡 기준" --preserve motif:a
python -m musigen piece "K:\Music Generation-codex\output\p4\inputs\v002" --out "K:\Music Generation-codex\output\p4\after_rain" --feedback "중간이 조금 산만해요" --interpretation "12–16마디 음 수를 줄이고 긴 음 중심으로 정리한다. 14마디의 최고음과 원래 반주는 보존한다." --preserve bars:1-8 bars:17-24 lh:1-24 motif:a motif:b
python -m musigen piece "K:\Music Generation-codex\output\p4\inputs\v003" --out "K:\Music Generation-codex\output\p4\after_rain" --feedback "마지막을 더 여운 있게" --interpretation "23마디를 두 음으로 정리하고 종결 화음에 테누토와 유지 페달, 마지막 두 마디에 diminuendo를 둔다." --preserve bars:1-22 motif:a motif:b
```

| 버전 | 변경 마디 | 연결부 | 보존 위반 |
|---|---|---|---|
| v001 | None | [] | [] |
| v002 | {'rh': [12, 13, 14, 15, 16], 'lh': []} | [{'changed': [12, 16], 'before': 11, 'after': 17, 'before_changed': False, 'after_changed': False}] | [] |
| v003 | {'rh': [23, 24], 'lh': [23, 24]} | [{'changed': [23, 24], 'before': 22, 'after': None, 'before_changed': False, 'after_changed': False}] | [] |

청취 페이지: `K:\Music Generation-codex\output\p4\after_rain\listen.html`.
v001→v002는 11–17마디, v002→v003은 22–24마디에서 비교합니다. 피드백은 명세가 정한 가상 문장으로 실제 사용자 청취 승인으로 기록하지 않았습니다.

## 위험
6도 판정은 현재 조성의 가까운 음계 단계이며 반음 수의 임의 임계가 아닙니다. 시간표/표현을 포함하므로 표현만 바뀌어도 양손이 변경으로 표시될 수 있습니다. --latest 페이지에는 부모가 없어서 비교 버튼이 비활성입니다. 페이지는 브라우저 Web Audio 미리듣기이며 사람의 연주 판정은 남아 있습니다. MuseScore 미확인.

## 검수
Claude 검수 대기.

브라우저 추가 검증: Chrome에서 v001/v002/v003 모두 Verovio 로그 빈 문자열. 부모→현재 비교 범위 22–24마디(57273–65455ms), 변경 배경 2마디, 수동 정지와 오류 0 확인. output/p4/compare.png를 육안 확인했습니다.
