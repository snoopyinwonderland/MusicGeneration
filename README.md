# MUSICANOTE Virtual Composer

말로 쓴 요청에서 새 피아노 곡을 만듭니다. 지금은 대화에서 작곡 설계와 악보를 작성하며, 검증·기보·감상·다운로드는 코드가 맡습니다. 내부 Python 패키지와 실행 명령 `musigen`은 호환성을 위해 유지합니다.

기존 리드시트 실험도 함께 남아 있습니다:

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

### 듣기 페이지

[듣기 페이지](docs/listen/index.html)는 새 곡 **빛이 머무는 자리**의 피아노 솔로·바이올린–피아노 듀엣과 기존 시험곡 네 곡을 담습니다. 위쪽 메뉴에서 곡과 편성을 고릅니다. 「겨울 아침」은 Codex가 기보 기능 검증용으로 작성한 시험곡입니다.

- 악보를 보면서 재생할 수 있습니다. 음표를 누르면 그 위치부터 재생합니다.
- 빠르기를 바꾸거나 한 손만 들을 수 있습니다.
- 작곡 설계(요청/제안 표시)와 자동 검사 결과도 함께 보입니다.

여는 방법은 두 가지입니다.

- 독립 HTML은 내려받아 브라우저에서 엽니다. `--shared-assets`로 만든 공개 페이지는 HTTP로 제공해야 합니다. `python -m http.server 8000 --directory docs`로 시작하고 `http://localhost:8000/listen/`을 엽니다. Verovio는 인터넷(jsDelivr)에서 불러옵니다.
- 저장소 설정에서 GitHub Pages를 `main` 브랜치의 `/docs`로 켭니다. 그러면 `https://snoopyinwonderland.github.io/MusicGeneration/listen/`에서 바로 열립니다.

`piece` 명령은 버전을 만들 때마다 `output\<곡>\listen.html`(모든 버전, 최신이 먼저)을 새로 씁니다. 따로 만들려면 다음 명령을 씁니다.

```powershell
python -m musigen listen output\after_rain --out docs\listen\index.html --latest
python -m musigen listen output\after_rain --out x.html --embed-verovio "K:\Music Composition\node_modules\verovio\dist\verovio-toolkit-wasm.js"   # 인터넷 없이 (약 7MB)
```

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

## 곡별 주소와 피아노 음원

```powershell
python -m musigen listen output/p3/after_rain output/p3/winter_morning --out docs/listen/index.html --latest --individual-pages --piano-samples
```

`--individual-pages`는 `listen/<곡 폴더>/index.html`과 `listen/<곡 폴더>/v001.html`, `catalog.json`을 만듭니다. 같은 곡 폴더 이름을 유지하면 곡 주소가 유지됩니다. 버전 고정 주소는 그 버전 악보만 표시합니다. 통합 페이지에서도 ‘이 악보 주소’가 곡과 버전을 지정합니다. 여러 버전 비교는 부모 버전도 포함하도록 --latest를 빼고 생성합니다.

`--piano-samples`는 선택 옵션입니다. 공개 예시에는 켰으며 일반 빌드는 기존 합성음을 유지합니다. 페이지의 ‘샘플 WAV 받기’는 선택한 손·빠르기·페달·셈여림을 적용한 음원과 출처 파일을 저장합니다. 기본 빌드는 샘플을 HTML에 포함하고, `--shared-assets` 빌드는 같은 사이트의 공통 파일을 읽습니다. 별도 음원 서버에는 접속하지 않습니다. Verovio는 기본적으로 CDN에서 읽습니다. 음원 저작자·라이선스·변경 내역은 [출처](musigen/assets/piano/ATTRIBUTION.md)에 있습니다.

Claude가 검수 후 docs를 병합하면 기존 GitHub Pages에서 `/MusicGeneration/listen/after_rain/`, `/MusicGeneration/listen/winter_morning/` 경로로 열립니다. Codex는 main을 수정하거나 push하지 않습니다. 병합 전 검수는 공개 브랜치 커밋의 `raw.githack.com/snoopyinwonderland/MusicGeneration/<커밋>/docs/listen/<곡>/index.html` 주소를 사용합니다. 제3자 미리보기 서비스라 GitHub Pages 운영 주소와는 구분합니다.

최종 검수판은 최신 main의 햇살 골목·모퉁이 카페도 포함합니다. 생성 루트는 `output/p5/after_rain output/p5/winter_morning output/p5/sunny_alley output/p5/corner_cafe`입니다. 최신 main의 보표별 성부 번호와 스윙을 유지하며, 1차 꾸러미와의 바이트 기준 차이는 검수서에 기록했습니다.


## 새 곡과 듀엣, 악보 다운로드

「빛이 머무는 자리」는 이 요청에 맞춰 Codex가 새로 쓴 곡입니다. D장조·3/4·♩=72·24마디·60초이며, 제목·정서·형식·음은 작곡 제안입니다. 청취 승인을 받은 완성작으로 표시하지 않습니다.

```powershell
python -m musigen piece examples/pieces/lingering_light --out output/my_solo --feedback "새 악보 한 개만 만들어 보죠."
python -m musigen duet output/my_solo/v001 --out output/my_duet
$env:MUSICOMP_ROOT = "K:\Music Composition"
$env:CHROME_PATH = "C:\Program Files\Google\Chrome\Application\chrome.exe"
node scripts/render_score_pdf.cjs output/my_solo/v001 output/my_duet/v001
python -m musigen listen output/my_solo output/my_duet --out docs/listen/index.html --latest --individual-pages --piano-samples --shared-assets
```

PDF 생성은 musicomp 쪽에 설치된 `verovio`와 `playwright-core`를 읽습니다. `CHROME_PATH`를 생략하면 Playwright에 설치된 Chromium을 사용합니다. MusicXML을 같은 Verovio로 그린 벡터 PDF이며 PDF 생성 뒤 `listen`을 다시 실행하면 받기 버튼이 연결됩니다. PDF가 없는 버전은 버튼을 비활성화합니다. MusicXML은 원본 바이트 그대로, PDF는 저장된 파일을 내려받습니다. 화면의 빠르기·음소거는 악보 파일을 바꾸지 않습니다. 샘플 WAV에는 재생 설정이 반영됩니다.

`duet`은 선택 명령입니다. 솔로 오른손 첫 성부의 음높이·길이·이음줄·아티큘레이션을 바이올린으로 옮기고, 오른손 안쪽 성부와 왼손을 피아노에 남깁니다. 단선율 및 G3–A6 범위를 확인하며, 여러 음짜리 주선율은 임의로 버리지 않고 거부합니다. 셈여림은 두 악기에, 페달과 원래의 글자 지시는 피아노에 남깁니다. 활 배분·운지·실제 연주 가능성의 세부 검수는 다음 단계입니다. 범용 앙상블 편곡기는 아닙니다.

페달 구간의 선택 필드 `release`는 4분음표 단위로 마지막 떼는 시점을 앞당깁니다. 예: `{"bars":"1","pedal":"held","release":"1/4"}`. 현재 수정곡에서는 프레이즈 끝의 쉼에서 페달도 떼고, 나머지 마디는 16분음표만큼 먼저 떼며 마지막 마디는 끝까지 밟습니다. 기본값 0이며 기존 악보 출력은 유지합니다. 재생은 첫 페달 교체 지점에서 이전 음을 끊고 바이올린에는 페달을 적용하지 않습니다.

공개 예시의 음원과 PDF는 `docs/listen/assets/`를 공용으로 씁니다. 일반 작업 출력은 `output/`에 두고 Git에 넣지 않습니다. 공개 다운로드용 PDF만 자작곡의 배포 자산으로 포함합니다. 바이올린 샘플 출처는 [라이선스와 변경 내역](musigen/assets/violin/ATTRIBUTION.md)에 있습니다. 바이올린 지속음은 약식 루프이며 실제 활 표현을 재현하지 않습니다.

재생 회귀 검사는 `node --test scripts/test_playback.cjs`로 실행합니다.


## 프레이즈와 화성 표기

「빛이 머무는 자리」 수정판은 선율의 쉼 9곳, a–b 주제, 상행 반복·음가 확대·재현·단편 종결을 사용합니다. 반주는 왈츠형, 분산화음, 베이스, 알베르티, 셸 보이싱으로 구간의 역할을 구별합니다. ‘프레이즈와 주제’에서 구간을 누르면 해당 마디만 들을 수 있습니다.

설계에서 `"analysis":{"phrases":true}`를 켜면 기존 musicomp 프레이즈·동기 분석을 그대로 호출합니다. `phrase_plan`은 작곡자가 세운 계획이고, `checks.phrasing`은 실제 음과 쉼에서 관찰한 결과입니다. 기본은 꺼짐이며, 이 예시에서 여섯 경계가 맞는다고 일반적인 분석 정확도나 청취 품질이 입증된 것은 아닙니다.

화성 버튼은 **Chord Symbols · 코드 심벌**(D, A7, D/F♯ 등)과 **Roman Numeral Analysis**(I, V⁷, I⁶ 등)를 오갑니다. 로마자 표기는 기보 화음·국소 조성·화음 시작 때 실제 최저음으로 계산합니다. 화음 인식 엔진을 재학습하거나 바꾼 것이 아닙니다. 첨가6음은 `(add6)`, 제1전위는 `⁶`로 구별합니다. 표기 전환은 화면에 적용되며, MusicXML/PDF 다운로드는 원본 코드 심벌 악보입니다.

페달은 밟고 있는 길이와 떼는 위치를 보여 주는 선 표기를 유지합니다. 벌어지는 `<`·`>` 헤어핀은 셈여림 변화이며 페달과 별개입니다.


## MusicXML에서 모티프 가져오기

듣기 페이지의 **모티프 작업실** 버튼을 누릅니다. MusicXML(.musicxml/.xml) 파일 또는 현재 악보를 열고, 파트·보표·성부를 고른 다음 시작과 끝 음을 선택합니다. 선택 상자를 써도 되고 악보의 음표를 눌러도 됩니다. ‘선택 구간을 모티프로’ → ‘모티프 듣기’ → ‘모티프 복사’ 또는 ‘모티프 JSON 받기’ 순서로 확인합니다. 다른 페이지·기기에서도 JSON 파일을 열거나 보관함에 붙여넣어 다시 사용할 수 있습니다. 클립보드 권한이 없으면 Ctrl+C/Ctrl+V를 사용합니다.

복사 내용은 음이름·정확한 분수 음가·쉼과 출처 구간을 가진 텍스트입니다. 파일은 브라우저 안에서 처리하며 서버로 보내지 않습니다. 현재는 비압축 score-partwise MusicXML과 MUSICANOTE 모티프 JSON을 받습니다. .mxl, MuseScore/Sibelius 등의 전용 클립보드 형식, PDF·이미지는 지원하지 않습니다. 해당 프로그램에서 MusicXML로 내보내서 여는 경로를 사용하세요.

저장한 모티프는 기존 발전 연산으로 곧바로 미리보기 악보를 만들 수 있습니다.

```powershell
python -m musigen motif a.motif.json --out output/motif_study --key D --mode major --meter 3/4 --ops step:1 aug:2
```

결과는 `motif.json`, `design.json`, `score.json`, `piece.musicxml`, `piece.mid`입니다. 기존 폴더를 덮어쓰지 않습니다. 이 명령은 모티프 변형의 미리보기이며 완성곡 자동 작곡은 아닙니다. 원본 모티프 JSON과 ‘이 주제로 조용히 시작해서 중간에 확대해 주세요’ 같은 요청을 대화로 주면, 작곡 설계에서 원형·변형·반주·종지를 구성합니다. `score.json`의 `motifs.a`에 복사한 객체를 그대로 넣어 기존 `motif`/`ops`/`seq` 문법으로 발전시킬 수도 있습니다.

화성 표시의 ‘위치’는 기본 **보표 아래**이며 피아노 낮은 보표 밑에 놓습니다. 코드 심벌·로마자 모두 적용하고 ‘원래 위치’로 돌아갈 수 있습니다. 이것은 화면 배치 설정이며 다운로드하는 MusicXML/PDF 원본은 바꾸지 않습니다.


## 기존 피아노 자료 활용 (선택 기능)

`piece --corpus-accompaniment`는 기존 피아노 반주 라이브러리와 밀도 모델을 사용해, 계획한 반주 유형 안에서 왼손 패턴을 선택합니다. 주제·오른손·화성·표현은 보존하고 결과와 출처를 고정 저장합니다. 기본은 꺼짐이며 청취 품질 검수 전입니다. [사용법·자료 범위·제한](docs/CORPUS_ACCOMPANIMENT.md)을 확인하세요.
