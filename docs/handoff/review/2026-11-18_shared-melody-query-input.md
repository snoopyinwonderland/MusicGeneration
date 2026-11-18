# MusicSearch 공유 입력기 0.1.0 적용 검수

`codex/shared-melody-query-input` · 기준 `8c151df` · [작곡 작업실](http://127.0.0.1:8808/compose.html)

사용자가 지정한 `K:/MusicSearch/packages/melody-query-input/README.md`와 배포 tarball을 확인하고, 작곡 작업실의 자체 입력기를 배포 패키지로 교체했다. `editor/vendor/musicanote-melody-query-input-0.1.0.tgz`는 원본과 SHA-256 `b350e4e8c67c2474d79dcd64b6585934637f1e00b25fb28cff9c7487b42e1e59`가 같다. 새 체크아웃에서는 저장소 루트에서 `pnpm --dir editor install --frozen-lockfile`을 실행한 뒤 작업실을 시작한다.

## 변경과 실행 범위

- `editor/index.tsx`에서 패키지의 `MelodyQueryInput`과 `style.css`를 가져온다. 패키지가 건반·악보·음가 슬라이더와 −/+·붙임줄·잇단음표·Undo/Redo·Query 복사/불러오기를 담당한다. 작곡기는 패키지의 `value`, `onChange`, `onPreview`로 현재 모티프와 피아노 음원을 연결한다.
- `editor/model.ts`에서 기존 모티프 v1과 패키지 이벤트를 변환한다. MIDI 음높이만 있는 Query, 쉼표, 붙인 음의 실제 길이, 이전 버전의 기보 정보와 잇단음표 비율을 처리한다. 새 Query를 불러오면 이전 악보의 출처를 이어 붙이지 않는다.
- `musigen/workshop.js`, `workshop.html`에서 직접 입력, 자동 생성, 리듬 변주, 파일 구간 붙여넣기, 저장된 곡 재열기를 연결했다. ‘이전 모티프와 전환’으로 자동 생성과 가져오기 전후를 비교할 수 있다. ‘마디별 입력 악보 보기’는 긴 음·마디 경계를 확인하는 기존 정밀 MEI 조판을 사용한다.
- `editor/build.mjs`, `package.json`, 잠금 파일과 `musigen/studio.py`는 패키지 JS·CSS 및 동적으로 불러오는 Verovio 모듈을 함께 빌드해 작업실에서 제공한다. 자체 건반·음표 편집 UI를 제거했다.

## 검수 위치와 결과

8808 작업실의 첫 마디에서 C4–D4–E4를 입력하고 첫 음의 길이를 바꾼 뒤 Undo/Redo를 확인했다. 두 번째 음을 위로 끌어 E4로 바꾸고, 연속한 E4 두 음을 Tie로 연결해 2박짜리 E4가 작곡 입력에 전달되는 것을 확인했다. 검은 건반에 초점을 둔 Enter·Space는 각각 C♯4 한 개를 입력했다.

패키지의 ‘Query 붙여넣기’에 E♭4–쉼–G4를 넣고 Query JSON으로 복사해 MIDI 63을 확인했다. 검증용 화면에서 MIDI, MXL, 일반 MusicXML의 구간을 실제 클립보드로 복사해 기존 모티프 JSON 칸에 붙여넣었다. MIDI의 G4–쉼–A4, MXL의 C3–쉼–D3, XML의 E♭4–쉼–F4 세 사건을 확인했다.

패키지와 곡 설정 사이의 박자 동기화, 미리 듣기, 마디를 넘는 E♭4의 붙임줄 표시, 자동 모티프·리듬 변주·이전 모티프 복원, 390px 화면을 실제 브라우저에서 확인했다. 검증용 작업실에서 편집한 모티프로 새 곡을 저장했고, 8808에서 기존 4중주와 해당 모티프를 다시 열었다.

TypeScript 엄격 검사와 편집기 테스트 8개가 통과했다. Python 전체 291개 중 290개 통과했다. 이전 꾸러미와 같은 `test_phrase_observations_have_real_breaths_and_all_notes`에서 외부 프레이즈 분절이 4구절이고 기대값은 6구절이다.

## 적용과 제한

8808의 기본 악보 입력기로 적용했다. 패키지의 선율·리듬·윤곽 입력과 별개로 곡 생성기는 3/4·4/4·6/8과 24분할 격자에서 최소 1/12박인 음가를 받는다. 범위를 벗어난 편집은 안내를 표시하고 이전 모티프를 유지한다. 패키지 입력 악보는 짧은 Query 표시용이다. 긴 음의 마디선 분할이나 복합 음가의 정확한 기보는 마디별 입력 악보에서 확인한다. 허밍 버튼의 실제 마이크 녹음은 검증하지 않았다.
