# 검수 요청: 사용자 모티프 기반 피아노 솔로 「창가에 머문 노래」

- 브랜치: `codex/motif-windowlight` (선행 `codex/breeze-selective-pedal` bbae092에서 분기)
- 요청: 사용자가 제공한 musicanote-motif JSON으로 피아노 솔로 한 곡 작성.
- 상태: 로컬 악보·음원 완성 초안, 기술 검증 완료 / 사용자 청취 검수 전.
- 엔진·main 변경 없음. 검수 문서만 새로 커밋. 사용자 제공 선율과 파생 악보·생성 스크립트는 AGENTS.md에 따라 로컬 output에 보관.

## 설계와 출처

- E♭장조, 4/4, 4분음표 84, 28마디, 약 80초, 6급 기준.
- 제공 출처: `Your Song Melody.musicxml.xml`, P1/보표1/성부1, 5마디 offset1부터 12마디 offset1까지. 원본 전체 파일은 열지 않았으며 제공한 JSON만 사용.
- 33사건·28박. 첫 등장 1마디 두 번째 박부터, 재현 17마디 두 번째 박부터 음높이·음가·쉼·순서를 정확히 보존. 모티프는 사용자 제공이고 화성·반주·발전·코다는 Codex의 새 제안.
- 1–8 제시, 9–16 첫 조각의 음가 확대와 상행 이동 및 13마디 B♭5 절정, 17–24 원형 재현, 25–28 짧은 조각과 정격종지.
- 5·21마디 Cm(add9), 9마디 A♭(add9)는 반복되는 선율의 9음 색채를 포함한 선택. 원곡의 화성을 복원했다고 주장하지 않음.
- 16마디 첫 두 박, 28마디 첫 세 박만 페달. 전체 112박 중 5박(4.46%, 약 3.57초). 나머지는 무페달.

## 사용한 데이터와 전후 비교

- 기존 피아노 코퍼스와 pacing 모델을 선택 옵션으로 사용. 새로운 학습 없음.
- 10곡에서 23마디에 자료 반주 적용. 8·16·24·27·28마디 직접 기보 보존. 라이브러리·모델 지문, 출처·마디·비용은 `accompaniment.json`에 기록.
- 기준 v001: 작성한 기본 음형. 결과 v002: 같은 선율·화성·표현에 자료 반주 적용. 오른손 두 성부 전 마디·주제 a 보존 약속 통과.
- `K:\Music Generation-codex\output\motif-windowlight\windowlight\v001`
- `K:\Music Generation-codex\output\motif-windowlight\windowlight\v002`
- 감상·다운로드: http://127.0.0.1:8791/listen/windowlight/v002.html
- 이전 비교본: http://127.0.0.1:8791/listen/windowlight/v001.html
- PDF 2페이지, XML, MIDI, 실제 샘플 피아노 WAV 및 음원 attribution 제공. 서버는 로컬 127.0.0.1:8791이므로 실행 중인 이 PC에서 사용.

## 검증

- 전체 Python 테스트 92개 통과. 기능 코드 변경 없으므로 테스트 추가 없음.
- 두 버전 모두 악보 검사 오류 0, 경고 0. 자동 통과는 청취 승인과 다름.
- 입력 모티프의 실제 Note 시간·음높이·음가와 제시/재현을 직접 대조. 모든 음 및 음 사이 쉼 보존. `motif-preservation.json` 참조.
- 프레이즈 분석 사용: 상위 끝 경계 4·8·12·16·20·24·28마디가 설계와 일치. 자동 시작 마디는 여린박 시작 때 다음 마디로 표시되는 기존 관찰 convention이 있어 원래 start 시간도 함께 기록. 오른손 첫 성부 쉼 총 27박.
- 자료 적용 후 오른손 103개 Note 사건, 왼손 75개. 브라우저는 화음의 개별 음을 세어 204음. 서로 다른 집계 단위.
- 브라우저 재생/정지, Roman/Chord 표시 전환 시 음표 보존, XML/PDF/WAV 받기 확인. JS/Verovio 오류 없음. 샘플 30개, 페달 기호 4개 모두 표시.
- WAV 44.1kHz, peak 0.3416, RMS 0.03349, clipping 0. 음악 길이 79.998초, WAV는 릴리스 꼬리가 추가됨.
- PDF 두 페이지 시각 검수 및 페이지별 제목·다운로드 바이트 일치 확인. 페이지별 독립 렌더링 후 병합. 원본 XML의 음표·기호는 변경하지 않고 PDF 렌더링 입력에만 4마디마다 시스템/17마디 페이지 나눔 추가.
- 근거: `v002/checks.json`, `composition-summary.json`, `motif-preservation.json`, `qa/browser.json`.

## 변경 파일·재현·한계

- 새 추적 파일은 이 검수 요청서뿐. 기존 생성기, musicomp, 분석 계수·라이브러리 미수정. 곡별 엔진 예외 없음.
- 로컬 `output/motif-windowlight/work`에 입력 motif/design/score, `selected.json`에 고정 자료 반주. `qa`에 생성·검증·PDF 스크립트 보관. v002의 design/score로 build할 때 코퍼스 재선택 없이 동일 음표 재생성 가능.
- PDF 출력 스크립트는 페이지별 PDF를 만들며 pypdf.PdfWriter로 순서대로 합친 결과가 최종 piece.pdf. 다운로드 페이지는 최종 PDF 생성 후 다시 빌드함.
- 샘플 음원은 실제 피아노의 페달 공명 전체를 재현하지 않음. 반복 재현이 충분히 변화 있게 들리는지는 사용자 청취로 확인해야 함.
- 기본 동작·기본 곡 변경, GitHub Pages 게시, main push 없음. 선행 c8a8b62의 선택적 Ped./* 출력 기능을 사용.
