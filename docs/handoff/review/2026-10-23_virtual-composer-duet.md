# MUSICANOTE Virtual Composer: 새 솔로·듀엣과 감상 화면 검수 요청

- 작업 브랜치: `codex/virtual-composer-duet`
- 기준 main: `148ea31` (2026-10-23). musicomp는 병합된 main `c361a87`을 읽기만 사용.
- 상태: 구현·자동 검사·브라우저 다운로드·PDF 시각 검수 완료. 사용자 청취 검수 및 Claude 병합 전. main push 없음.
- P1–P5는 main에 병합된 상태에서 시작했으며 이번 사용자 요청을 별도 꾸러미로 진행.

## 요청과 결과

사용자 원문: “새 악보 한 개만 만들어 보죠. xml, pdf 받기 버튼도 있으면 좋겠네요. musigen이라는 이름은 MUSICANOTE Virtual Composer로 바꾸죠. 웹 디자인도 조금 넣어 주면 좋겠습니다.” 이어 “일단 솔로 만들고 그걸로 바이올린-피아노 듀엣을 만들어 보죠.”

새 작곡은 **빛이 머무는 자리** 한 곡. D장조·3/4·♩=72·24마디·60초, Codex 작곡 초안. 조성·제목·장면·주제·형식은 제안이며 사용자 지정으로 기록하지 않았다. 솔로를 먼저 쓴 뒤 동일 음표를 바이올린/피아노로 분담했다. 기존 「겨울 아침」은 Codex가 기보 기능 시험용으로 작성한 곡임을 명시했다.

## 바꾼 파일과 역할

| 파일 / 함수 | 변경 |
|---|---|
| `examples/pieces/lingering_light/` | 새 설계·악보. 선율, 안쪽 응답, 낮은 펼침화음. 24개 페달 구간 |
| `musigen/piano_io.py:piano_part` | 기존 피아노 파트 작성을 분리해 듀엣에서 재사용. 기본 XML 바이트 보존 |
| `musigen/duet.py:parts, write_duet, save_duet` | 선택 명령 `duet`. 오른손 1성부를 바이올린으로 옮김. 다성 주선율·음역 밖은 오류. 음/리듬/이음줄/아티큘레이션 보존 |
| `musigen/expression.py:compile_expression` | 선택 필드 `release`로 페달 종료만 앞당김. 같은 행의 hairpin 종료는 유지 |
| `musigen/listen.py` | `--shared-assets`로 공통 음원·PDF 제공, 독립 HTML은 계속 포함 방식. PDF 없는 버전은 버튼 비활성화 |
| `musigen/listen_template.html` | 브랜드·반응형 디자인, MusicXML/PDF/샘플 WAV 받기, 재생 음원, 듀엣 악기 분리, 바이올린 샘플 재생, 페달 교체 버그 수정 |
| `musigen/assets/violin/` | FluidR3_GM CC BY 3.0 US, 원본/변경/해시/라이선스 기록. 기존 Analysis의 검증된 은행을 읽어 복사 |
| `musigen/design.py`, 겨울 아침 설계 | 선택 credits 허용, 작곡 주체 표시 |
| `scripts/render_score_pdf.cjs` | 같은 MusicXML → Verovio SVG → Chrome 벡터 PDF. XML 후처리 없음 |
| `scripts/test_playback.cjs`, `tests/test_virtual_composer.py` | 페달 교체·바이올린 제외, 음표 보존, 거부 입력, 공통 자산·독립 PDF 회귀 |
| `scripts/check_listen.cjs` | 로컬 HTTP로 6편성 렌더·재생·다운로드, 개별 주소 및 모바일 검증 |
| `docs/listen/` | 새 곡 2편성 + 기존 시험곡 4곡. 자작 악보 PDF 6개와 공통 샘플. output 디렉터리는 Git 제외 |

## 전후와 들어 볼 곳

최종 생성 루트: `K:\Music Generation-codex\output\virtual-composer-release`.

- 솔로: `lingering_light/v001` (PDF 1쪽). 1–8마디 질문·응답, 9–16마디 상승과 하강, 17–20마디 재현, 21–24마디 종결.
- 듀엣: `lingering_light_duet/v002` (PDF 2쪽), source=`lingering_light/v001`. 바이올린 59개 + 피아노 164개 = 솔로 223개. 음높이·시점·길이 동일. 초기 v001은 피아노 글자 지시가 바이올린에도 복제되어 v002에서 수정했다. 초기 출력은 output에 보존, 공개 목록에는 최종판만 포함.
- 솔로 초안 `output/virtual-composer/lingering_light/v001`의 4·8·16·20마디 손 교차를 낮은 베이스 배치로 해결. 곡의 악보 데이터를 고쳤으며 곡 이름 분기나 검사 예외는 추가하지 않았다.
- 새 곡은 매 마디 끝 16분음표 전 페달을 떼고, 마지막 마디는 끝에서 뗀다. 실제 XML start/stop 24쌍 및 PDF 괄호 확인. 듀엣의 페달은 Piano에만 존재.
- 기존 「겨울 아침」의 첫 온마디 음이 페달 교체 이후에도 누적 연장되어 약 65.5초 지속되던 브라우저 버그를 수정. 원래 건반 릴리스 시점으로 첫 교체 경계만 찾도록 했다. 수정 후 같은 음의 지속은 2.728초. 기존 MusicXML과 작곡 데이터는 그대로.

공개 파일 경로는 `/listen/lingering_light/`, `/listen/lingering_light_duet/`. 버전 고정 주소는 각각 `v001.html`, `v002.html`. Claude 병합 전에는 이 브랜치 커밋의 raw.githack 미리보기를 사용한다. 최초 외부 링크 안내에서는 Open the page를 눌러 진입할 수 있다. GitHub Pages main 배포를 이번 작업에서 바꾸지 않았다.

## 검증

- `python -m unittest discover -s tests`: **61개 통과**. 기존 after_rain 최신 main XML 기준 바이트 회귀 통과.
- `node --test scripts/test_playback.cjs`: **4개 통과**. 연속 페달 교체/인접 구간/바이올린 미적용/기본 길이.
- `node scripts/check_listen.cjs` (MUSICOMP_ROOT, CHROME_PATH 지정): Chrome 6편성 모두 Verovio log 비어 있음, JS 오류 0. 개별 주소, 재생/멈춤, 바이올린 음소거, 390px 모바일 가로 넘침 없음 확인.
- 솔로/듀엣 MusicXML·PDF·WAV 버튼을 실제로 눌러 저장. XML은 페이지 원문과 동일. PDF 헤더 확인. 60.5초 WAV(잔향 포함)는 무음/클리핑 없음: peak 0.342 / 0.351, RMS 0.0479 / 0.0444. 이는 파일 검사이며 청취 승인을 뜻하지 않는다.
- 피아노 30개, 바이올린 27개 샘플 정상 디코드. 새 곡 첫 피아노 음은 페달로 2.292초, 바이올린 음은 0.791초로 유지되어 악기 분리 확인.
- 새 솔로 자동 검사 오류 0, 경고 0. 7·15·23마디 경과음은 참고로 남김. 듀엣의 화성/동기 검사는 원본 솔로 기준임을 표시.
- PDF 6개 총 9쪽을 Poppler PNG로 렌더링해 시각 확인. 새 솔로·듀엣의 페달, 한글 제목, 끝마디, 쪽 번호 확인.
- 증거: 위 output 루트의 `browser-check.json`, `solo-desktop.png`, `duet-desktop.png`, `duet-mobile.png`, `pdf-review/`, 다운로드한 MusicXML/PDF/WAV.

## 한계와 검수 요청

- 이번 듀엣은 선율 분담의 첫 단계. 운지·활 배분·현 선택·주고받기 편곡을 자동 완성한 것이 아니다. 새 작곡의 정서·반복·저음 균형은 실제 청취 의견을 기다린다.
- 바이올린은 한 벨로시티 층의 근접음 샘플과 약식 지속 루프다. 활/비브라토/레가토 전환을 사실적으로 모델링하지 않는다. 피아노 페달은 소리 길이 연장으로 근사하며 공명·기계 소리까지 합성하지 않는다.
- ‘재생 음원’은 샘플과 합성음을 선택한다. ‘샘플 WAV 받기’는 선택한 악기 음소거·빠르기로 **샘플 음원**을 저장한다. 악보 다운로드는 재생 설정을 반영하지 않는다.
- 공통 자산을 쓰는 공개 페이지는 HTTP 환경이 필요. 일반 standalone 빌드는 기존처럼 샘플과 PDF를 포함할 수 있다. 악보 엔진은 기본 CDN, 오프라인은 `--embed-verovio`.
- MuseScore GUI와 실연은 이번에 확인하지 않았다. 모든 자동 PASS를 음악 품질의 승인으로 해석하지 말 것.
- main 병합 후 두 편성의 개인 URL과 PDF 버튼을 배포 서버에서도 확인해 주시기 바란다.
