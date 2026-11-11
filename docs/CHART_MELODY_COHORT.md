# 차트와 선율 관찰 표본 — 2026-11-11

인기 순위는 비교 표본을 고르는 근거다. 선율의 품질 점수나 인과관계, 모델 학습 라벨로 쓰지 않는다. 원 음표와 가사 본문은 저장소에 넣지 않는다.

## 출처와 집계 범위

- [TJ 2025 노래방 결산](https://www.tjmedia.co.kr/chart/hit_song): 2025-01-01–12-07 온라인 반주기 이용 횟수. TJ 번호를 금영 번호로 취급하지 않는다.
- [Billboard Canadian Hot 100 Songs, 2025 연말](https://ca.billboard.com/charts/year-end-2025/top-billboard-canadian-hot-100-songs): 캐나다 차트다. 미국 Hot 100 전체 연말 페이지는 접근하지 못했으므로 미국 순위로 대체 표시하지 않는다.
- [Classic FM 2025 Hall of Fame 상위 10곡 발표](https://www.classicfm.com/radio/hall-of-fame/karl-jenkins-armed-man-voted-highest-spot/): 2025-04-21 발표, 약 9만 청취자 투표. 판매량·스트리밍 차트가 아니다.

## TJ 상위 10곡과 로컬 연결

| 순위 | 곡 / 가수 | 확인할 금영 ID 또는 악보 |
|---|---|---|
| 1 | Drowning / WOODZ | 80979 |
| 2 | 나는 반딧불 / 황가람 | 55791 |
| 3 | 모르시나요 (Prod. 로코베리) / 조째즈 | 74798 |
| 4 | 천상연 / 이창섭 | 82628 |
| 5 | My Love (And) / 버즈 | 85066 |
| 6 | 응급실 (쾌걸춘향 OST) / izi | 45117 |
| 7 | 시작의 아이 / 마크툽 | 74745 |
| 8 | 남자를 몰라 / 버즈 | 85068 |
| 9 | Golden / HUNTR/X | Golden Melody.musicxml.xml |
| 10 | 사랑의 바보 / The Nuts | 64438 |

금영 연결은 `kumyoung-merged.json`의 제목·가수로 확인한다. Golden은 김은재·Mark Sonnenblick 작곡 표기가 있는 로컬 Melody 악보로 따로 연결한다. 최근곡은 메타데이터에 있어도 현재 MIDI에 없을 수 있으므로 실제 파일 유무와 S1/channel 4를 재검증한다.

## Billboard 캐나다 상위 10곡

1. A Bar Song (Tipsy) — Shaboozey
2. Ordinary — Alex Warren
3. APT. — ROSÉ & Bruno Mars
4. Die With a Smile — Lady Gaga & Bruno Mars
5. Beautiful Things — Benson Boone
6. That's So True — Gracie Abrams
7. I Had Some Help — Post Malone featuring Morgan Wallen
8. Pink Pony Club — Chappell Roan
9. Messy — Lola Young
10. Birds of a Feather — Billie Eilish

1·2·4·5·6·8·10위는 로컬 Melody 악보의 제목·작곡자 표기를 확인했다. 이 악보들은 편곡본의 주선율로, 상업 녹음의 원전사와 동일하다고 보장하지 않는다. 나머지는 연결 미확정으로 남긴다. 이름만 비슷한 작품을 결합하지 않는다.

## 클래식 투표 상위 10곡

Rachmaninov 피아노 협주곡 2번, Karl Jenkins The Armed Man, Vaughan Williams The Lark Ascending, 같은 작곡가의 Fantasia on a Theme by Thomas Tallis, Elgar Enigma Variations, Shostakovich 피아노 협주곡 2번, Allegri Miserere, Beethoven 피아노 협주곡 5번, Beethoven 교향곡 9번, Holst The Planets 순이다.

전체 악곡과 악장·발췌·편곡·다른 노래의 인용을 구별해야 한다. 이 상위 10곡의 역할이 확인된 주선율까지 연결하기 전에는 ‘인기 클래식 주선율 표본’을 분석했다고 보고하지 않는다. 일반 클래식 자료의 명시 성부 관찰과 기존 TAVERN/DCML의 검증한 구절·종지·국소 조성 자료는 별도 근거로 사용한다.
