# musigen 작업 규칙

먼저 읽을 것:
- `README.md`: 실행
- `docs/COMPOSING.md`: 피아노 소품 작곡의 흐름, 원칙, 파일 형식
- `docs/handoff/`: 코덱스 요청문. 최신은 `2026-10-23_PIANO_PIECE_CODEX.md`
- `docs/HANDOFF.md`: 리드시트 기준선의 구조와 한계

## 원칙
- 사용자에게 보이는 글은 한국어로 씁니다.
- 곡별 규칙은 만들지 않습니다. 규칙 옆에 근거(청취 의견 원문, 통계와 분모)를 적습니다.
- 출력이 바뀌는 새 동작은 처음에 선택 옵션으로 둡니다.
- 바꾸기 전후를 비교하고, 들어 볼 폴더와 마디를 보고합니다.

## 작업 순서 (코덱스)
1. 작업 트리와 브랜치에서 작업합니다. `K:\Music Generation`은 클로드의 작업 공간입니다.
   ```powershell
   git -C "K:\Music Generation" worktree add "K:\Music Generation-codex" -b codex/<주제> main
   ```
2. 테스트를 통과시킵니다: `python -m unittest discover -s tests`. Python은 `K:\Music Analysis\.venv\Scripts\python.exe`입니다.
3. 검수 요청서를 `docs/handoff/review/YYYY-MM-DD_<주제>.md`에 씁니다. 다음을 적습니다.
   - 무엇을 왜 바꿨는지
   - 바꾼 파일과 함수
   - 전후 결과(들어 볼 폴더·마디)
   - 위험
4. 브랜치에만 커밋합니다. 클로드가 검수해 main에 병합합니다. 저장소에는 아직 원격이 없습니다.

## 건드리지 않을 것
- musicomp(`K:\Music Composition`)는 불러 쓰기만 합니다. 고쳐야 하면 그 저장소의 `AGENTS.md` 절차를 따릅니다.
- `output/`, 저작권 악보, `.env`는 저장소에 넣지 않습니다.
- KYSing·AI Hub 국악 자료는 권한이 확인될 때까지 쓰지 않습니다. DCML은 선택 옵션으로만 씁니다.
