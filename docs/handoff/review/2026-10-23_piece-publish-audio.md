# 곡별 URL·피아노 음원 검수 요청

브랜치 `codex/piece-publish-audio`, P4 `f3fd011` 위에 쌓았습니다. 사용자의 추가 요청 “각 악보가 URL을 갖게 하고, 음원을 피아노 소리로 입혀 주세요”에 따른 꾸러미입니다. ROUND1의 샘플 제외 조건은 라이선스 선확인 후 이 추가 요청 범위에서 진행했습니다.

## 변경
- `listen.build_page/_write_page`, CLI `--individual-pages`: 곡별 index.html, 버전별 v001.html, catalog.json. 통합 페이지도 fragment로 곡·버전을 지정합니다. 같은 이름의 곡 입력은 거절합니다.
- CLI `--piano-samples`: 선택형 FluidR3 피아노 은행 포함. 기존 일반 빌드는 합성음 유지, 공개 예시만 피아노 옵션을 켰습니다. 피아노/합성음 선택과 WAV 저장 버튼이 있습니다.
- `listen_template.html`: AudioBufferSourceNode로 샘플을 재생, 자연 감쇠와 페달/주법 반영, OfflineAudioContext로 선택한 손·속도의 WAV 렌더링과 출처 파일 저장. 소리가 준비되지 않으면 피아노 재생을 막고 합성음 선택을 안내합니다.
- `musigen/assets/piano`: 30개 음의 샘플 은행, 해시·원본 출처 manifest, 저작자·라이선스·변경 내역. 공개 HTML에도 출처가 포함되어 파일 하나를 공유해도 출처가 남습니다.
- 검수 화면 조성 이름을 읽기 쉽게 표시하고 변경 마디 배경의 범위를 보표 중심으로 조정했습니다.

## 라이선스 확인
2026-10-23 upstream 고정 revision README에서 FluidR3 패키지의 CC BY 3.0 US 표시를 재확인했습니다.
원본: https://github.com/gleitz/midi-js-soundfonts/blob/044fab8e1456bfafc5776e86dfd6bb8697149aef/README.md
저작자 Frank Wen 및 기여자, 패키징 Benjamin Gleitzman. Music Analysis의 검증된 피아노 JSON만 읽기 전용 복사, 해시 일치 확인. 다른 악기/외부 플레이어 코드는 복사하지 않았습니다. WAV에 적용된 진폭 정규화·음 이동·음량/길이 조절도 표시했습니다.

## 검증
- Python 52→54개 통과. 전체 기존 회귀 포함. 공개 파일 경로, 개별 버전, 선택 옵션 기본값, 샘플 해시와 88건반 전체의 근접 이동 한도 검사.
- Chrome: 두 곡, 버전 고정 경로, fragment로 선택한 곡, 피아노/재생/정지/WAV 저장 확인. Verovio6.3 로그 빈 문자열, 페이지 오류 0.
- 30개 샘플 모두 디코딩·비무음. 실제 재생 소스는 모두 AudioBufferSourceNode.
- 겨울 아침 WAV: 66.409초, 5,857,318바이트, 최대 진폭 0.2898, RMS 0.0419.
- 비 갠 밤 WAV: 65.818초, 5,805,162바이트, 최대 진폭 0.3655, RMS 0.0355. 두 파일 모두 무음/클리핑 없음.
- `output/p4/after_rain/listen.html`도 피아노로 재생성해 부모→현재 비교·정지를 재확인. 가상 수정 버전은 output에만 있습니다.
- `output/piano-page.png`, `output/p4/compare.png` 화면 확인. WAV는 output/<곡>-v001-piano.wav와 출처.txt에 있으며 git에 넣지 않습니다.

## 들어 볼 주소와 재현
```powershell
python -m musigen listen output/p3/after_rain output/p3/winter_morning --out docs/listen/index.html --latest --piano-samples --individual-pages
```
곡별 파일: `docs/listen/after_rain/index.html`, `docs/listen/winter_morning/index.html`.
버전별 파일: 각 곡 폴더의 `v001.html`.
main 병합 후 운영 주소: `https://snoopyinwonderland.github.io/MusicGeneration/listen/<곡>/`.
병합 전 주소: `https://raw.githack.com/snoopyinwonderland/MusicGeneration/<이 브랜치 커밋>/docs/listen/<곡>/index.html`.
main과 GitHub Pages 설정은 변경하지 않았습니다. 제3자 브랜치 미리보기는 운영 배포와 구분합니다.
청취: 겨울 아침 0–8마디 주법·페달, 9–11마디 왼손 주제, 13–16마디 증감, 24마디 유지 페달. 비 갠 밤은 원래 음을 유지한 피아노 음색 비교.

## 위험과 남은 검수
샘플은 한 벨로시티 층이며 사람의 터치·공명 모델을 재현하지 않습니다. 진폭 정규화와 미리듣기 gain은 잠정 믹스입니다. 사용자의 실제 청취 승인 및 MuseScore4 검증은 아직 없습니다. HTML마다 샘플을 포함해 파일 크기가 약 1MB씩 늘어납니다. CDN Verovio가 필요한 경우 네트워크가 필요하며 --embed-verovio로 포함할 수 있습니다. --latest 결과는 부모 버전 비교를 제공하지 않습니다.

## 검수·병합 순서
musicomp `codex/xml-expression` (`eb882fe`) → MusicGeneration `codex/piece-notation` (`4974197`) → `codex/piece-theme` (`9237695`) → `codex/piece-checks` (`f5da065`) → `codex/piece-revision` (`f3fd011`) → 이 브랜치.
각 꾸러미 검수 요청서는 같은 폴더에 있습니다. 자동 검사 통과는 기본 적용 승인과 구분하며, main 병합은 Claude 검수 후 진행합니다.

## 작업 중 main 변경 통합 (최종)

최종 점검에서 Claude 작업 공간 main이 `95058ac`으로 진행된 것을 확인했습니다. `385ae68`(햇살 골목·블록 chords·보표별 성부), `95058ac`(모퉁이 카페·shell/walk/push·스윙)을 이 codex 브랜치에 병합했습니다. main에는 쓰지 않았습니다.

- 공개 대상은 네 곡: after_rain, winter_morning, sunny_alley, corner_cafe. 모두 `output/p5/<곡>/v001`에서 만든 개별 URL과 피아노 페이지가 있습니다. 위 두 곡 생성 명령 대신 네 output/p5 경로를 나열하면 최종 공개판을 재현합니다.
- 스윙은 최신 main의 2:1 동작을 유지하되 qMs 시간 대응으로 계산하고 표현 지시도 함께 적용합니다. 음원 저장에도 같은 노트 시간표를 사용합니다.
- 인식/연결부/검사에서 성부를 손+보표 안 번호로 구분했습니다. 최신 main의 왼손 1/2 번호가 오른손과 섞이지 않습니다.
- **원래 바이트 기준의 예외**: 최신 main의 성부 번호 수정이 왼손의 불필요한 온쉼표를 없애 XML을 바꿉니다. P1–P4의 옛 기준 파일은 보존합니다. 최종 회귀는 읽기 전용 main95058ac+musicomp main에서 직접 생성한 `tests/data/after_rain_main950_v001.musicxml`과 바이트 비교합니다. 새 표현을 사용하지 않으면 최신 main과 정확히 같습니다. 악보 음·리듬 변화는 없습니다.
- Python 56개(최신 main의 2개 포함) 통과. 네 곡 모두 Verovio 로그 빈 문자열, 재생·정지 오류 0. 새 예시들의 기존 작곡 경고는 자동 수정하지 않았습니다.
- `.gitattributes`로 샘플 해시와 XML 기준의 줄바꿈을 고정했습니다.

추가 음원 검증: 햇살 골목 63.902초(peak 0.4367, RMS 0.0544), 모퉁이 카페는 스윙 시간표로 샘플 재생·WAV를 생성했습니다. musicomp 최종 Node 4/Python 105개 통과(MUSICOMP_PYTHON을 지정).

공개 환경 추가 수정: 약 1MB의 내장 샘플 HTML이 내려오는 동안 Verovio WASM이 먼저 초기화되면 onRuntimeInitialized 콜백을 놓치는 경쟁 상태를 발견했습니다. 콜백 등록과 이미 준비된 runtime 초기화를 모두 지원하도록 수정했습니다. 로컬 파일·느린 공개 다운로드에서 모두 동작하도록 한 변경입니다. raw.githack 첫 방문은 외부 콘텐츠 안내의 ‘Open the page’를 눌러야 합니다. 최신 musicomp 의존성은 `269676b`입니다. 모퉁이 카페 WAV는 57.741초, peak 0.6079/RMS 0.0641로 클리핑이 없습니다.

최종 공개 검증(32bd57b): raw.githack의 안내에서 Open the page를 누른 뒤 네 개 곡 URL 모두 HTTP 200, 실제 CDN Verovio 로그 빈 문자열, 피아노 샘플 30개 준비, 재생/정지 성공, 모바일 폭 390px 가로 넘침 없음, 페이지 오류 0. 모퉁이 카페 약박 지연 75.833ms로 2:1 스윙 계산값과 일치했습니다. 공개 검수 URL의 커밋은 32bd57bf657f6cf8fcab244050b011fdd4bcca55로 고정할 수 있습니다.
