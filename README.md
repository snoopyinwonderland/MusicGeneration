# Music Generation (musigen)

말로 쓴 작곡 요청에서 새 곡을 만듭니다. 편곡이 아니라 작곡입니다.

- 조성, 박자, 형식, 화음, 마디별 요구를 받아 선율과 화음을 만듭니다.
- 결과는 리드시트(선율 + 반주 화음 파트)입니다.
- 원하면 [musicomp](https://github.com/snoopyinwonderland/MusicComposition)로 이어서 피아노 솔로, 듀엣, 트리오, 쿼텟으로 편곡합니다.

```
요청 문장 ──(언어 모델)──▶ 작곡 명세(JSON) ──▶ 화음 진행 ──▶ 선율 ──▶ 리드시트 MusicXML ──▶ musicomp 편곡
            prompt.py          spec.py         harmony.py   melody.py   score_io.py        compose.py
```

## 피아노 소품 작곡 (새 틀)

요청 문장에서 주제를 제시하고 발전시켜 완결하는 피아노 솔로 곡을 직접 씁니다. 흐름은 다음과 같습니다.

1. 작곡 설계(`design.json`)
2. 악보(`score.json`)
3. 검사와 버전 기록

```
요청 ──(작곡자)──▶ design.json ──▶ score.json ──▶ piece.musicxml / piece.mid ──▶ checks.json, history.md
                    design.py      piece.py        piano_io.py                 checks.py, versions.py
                                   (notation.py, motif.py, accomp.py)
```

```powershell
python -m musigen design examples\pieces\after_rain            # 설계표 (요청/제안 표시)
python -m musigen piece examples\pieces\after_rain --out output\after_rain --reason "첫 시험곡"
python -m musigen piece <작업 폴더> --out output\after_rain --reason "17마디부터 더 고조" --preserve bars:1-8 motif:a
```

흐름, 원칙, 파일 형식은 [docs/COMPOSING.md](docs/COMPOSING.md)에 있습니다.

## 설치

musicomp를 라이브러리로 씁니다. musicomp는 복사하지 않고 그 폴더를 경로로 읽습니다. 기본 위치는 이 폴더 옆의 `Music Composition`이고, 다른 곳에 있으면 `MUSICOMP_ROOT`로 지정합니다.

- Python 3.12, `pip install -r requirements.txt`. 개발 컴퓨터에서는 `K:\Music Analysis\.venv\Scripts\python.exe`를 씁니다.
- 편곡까지 하려면 musicomp의 반주 라이브러리와 캐시가 필요합니다. 설정은 musicomp README를 따릅니다.

## 실행

```powershell
# 명세 파일로 작곡 (examples/evening.json: F장조 4/4, 32마디 AABA)
python -m musigen compose examples\evening.json --out output\evening

# 편곡까지
python -m musigen compose examples\evening.json --out output\evening --arrange --grade 7 --style lyrical

# 다른 선율·진행
python -m musigen compose examples\evening.json --out output\evening_s2 --seed 2

# 문장으로 요청 (로컬 언어 모델, OpenAI 호환 주소)
$env:MUSIGEN_LLM_MODEL = "<모델 이름>"          # 예: Ollama에 올린 Qwen 모델
$env:MUSIGEN_LLM_BASE_URL = "http://localhost:11434/v1"
python -m musigen text "F장조 4/4, 빠르기 84, 32마디 AABA. B 부분에서 리듬을 촘촘하게, 21–22마디가 가장 높게." --out output\x
```

결과 폴더에는 다음이 생깁니다.
- `leadsheet.musicxml`: 선율과 화음 파트
- `spec.json`: 실제로 쓴 명세
- `result.json`: 마디별 화음과 음 수
- `arrangement/`: `--arrange`를 준 경우의 musicomp 결과. 작업 화면에서 열 수 있습니다.

## 명세

필드와 값은 [musigen/spec.py](musigen/spec.py) 위의 설명을 보세요. 마디 번호는 1부터 셉니다.
- 형식: 구간 이름(A, B…), 마디 수, 종지(authentic / half / plagal / none)
- 화음: 장르 통계(pop / jazz / classical)로 만들거나, 마디마다 직접 지정(`progression`)
- 마디별 요구: 음역 높게·낮게, 리듬 촘촘·차분·길게, 쉼, 화음 지정, 클라이맥스

## 테스트

```powershell
python -m unittest discover -s tests
```

## 현재 상태

기틀만 있습니다.

- 리드시트 기준선(`compose`/`text`): 규칙으로 선율을 만듭니다. 리듬 템플릿, 아치형 윤곽, 강박 화음음, 약박 음계 경과를 씁니다. 개선 방향은 [docs/HANDOFF.md](docs/HANDOFF.md)에 있습니다.
- 피아노 소품 틀(`design`/`piece`): 작곡자가 설계와 악보를 쓰면 검증, 출력, 검사, 버전 기록을 합니다. 다음 개발은 [docs/handoff/2026-10-23_PIANO_PIECE_CODEX.md](docs/handoff/2026-10-23_PIANO_PIECE_CODEX.md)에 있습니다.
