# 모티프 발전 비교 · 선택 실험

짧은 모티프를 발전시킬 때 원자료의 어떤 관계를 참고했는지 기록하고, 선율 이외의 조건을 고정한 두 감상본을 만듭니다. 대화에서 작성한 설계를 실현하는 `blueprint` 위의 선택 도구입니다. 기존 작곡 명령의 기본값을 바꾸지 않습니다.

## 관찰과 작곡을 구분

`musigen.variation_reference`는 로컬 [TAVERN](https://github.com/jcdevaney/TAVERN)의 사람이 나눈 악구 파일을 읽습니다. 작품마다 주제와 제1변주의 첫 악구만 비교합니다. 악구 번호가 같다는 것은 후보 대응이며, 주선율 역할이 동일하다는 인증이 아닙니다.

- 악보 `Krn/*_score.krn`에서 최상단 보표를 읽습니다. 화음, 성부 겹침, 장식음, 불명확한 박자, 서로 다른 길이·박자는 제외합니다. 최고음만 뽑는 선율 추정은 하지 않습니다.
- 붙임줄은 한 공격점으로 합칩니다. 음 수·쉼 길이·이웃음 왕복·주제 공격점의 동시 음고류 일치를 분모와 함께 기록합니다.
- `Joined`의 두 분석자 파일은 각각 경로와 해시를 기록합니다. 로마자 표기를 고쳐서 파싱하거나 분석자 둘을 같은 정답으로 합치지 않습니다.
- 자료와 라이선스의 SHA-256을 남깁니다. `parseData`로 읽으므로 원자료 폴더에 파서 캐시를 쓰지 않습니다.
- 모든 관찰은 `generation_eligible: false`입니다. 명시적으로 고른 관찰을 작곡자가 이번 비교 설계에 참고하는 것과, 전체 생성 라이브러리로 승격하는 것은 다릅니다.

이는 자동 프레이즈 경계 모델, 통계 학습, 검증 세트를 이용한 성능 평가가 아닙니다. 이전 P3의 경계 추출 검증 실패를 통과로 바꾸지 않습니다. BPS·MIDI·대중음악의 다른 자료도 이 명령으로 자동 생성에 투입하지 않습니다.

```powershell
$env:MUSICOMP_ROOT = 'K:\Music Composition'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'K:\Music Analysis\.venv\Scripts\python.exe' -B -m musigen.variation_reference --tavern 'K:\MusicSearch\data\classical-corpora\tavern' --out output\comparison-input\references.json
```

출력 파일은 새 경로여야 합니다. TAVERN 관찰 결과·인용에는 저장소의 CC BY-SA 4.0 라이선스와 출처를 유지합니다. 원곡 음열은 코드나 예제에 넣지 않습니다.

## 비교 입력과 검증

작업 폴더에 `motif.json`, `baseline.json`, `reference.json`, `references.json`, `decisions.json`을 둡니다. 두 설계는 `musicanote-development` v1 형식입니다. `decisions.json`에는 실제 관찰한 작품 ID, 적용 마디, 관찰 내용과 작곡자의 해석을 분리해 씁니다. 화면 문구는 `presentation`에 저장합니다. 곡 이름이나 마디별 작곡 규칙을 엔진에 고정하지 않습니다.

```powershell
& 'K:\Music Analysis\.venv\Scripts\python.exe' -B -m musigen.development_comparison --work output\comparison-input --out output\comparison-v003 --accompaniment output\comparison-input\common-accompaniment.musicxml --protected-bars 2
```

- 두 설계의 조성·박자·빠르기·화성·셈여림·표현과 보존 마디를 비교하고, 다르면 중단합니다.
- 기존 musicomp 피아노 XML의 왼손을 한 번 읽어 양쪽에 동일하게 붙입니다. 두 오선 한 파트 또는 명시적인 RH/LH 두 파트를 지원합니다. 비교 길이를 넘는 끝 음만 잘라냅니다.
- `멜로디 + 상세 화성`은 모든 구성음을 포함한 왼손 화음과 상세 sidecar를 제공합니다. `피아노 솔로`는 공통 왼손 위에 각각의 단선율을 붙인 비교용 독주입니다. 별도로 두 번 편곡한 완성작이라는 뜻이 아닙니다.
- 각 출력의 음·철자·음가·성부를 XML 재읽기로 확인합니다. 화성 요약은 구성음·베이스·시점·조성도 기존 `blueprint` 왕복 검사로 확인합니다.
- 기존 `musicomp.analysis.phrase.segment_layers`를 수정 없이 호출합니다. 결과는 관찰이며 청취 평가나 자동 선발 점수가 아닙니다.
- `comparison.json`에 보존 조건, 변경 마디, 입력 해시, 검사 경고를 기록합니다. `a/b_harmony.json`에 기능·종지 의도·베이스·전위·구성음·배치·선율 관계를 유지합니다.

PDF를 별도로 렌더링해 `a/b_melody_harmony.pdf`, `a/b_piano_solo.pdf`로 놓은 뒤 같은 명령에 `--pages-only`를 붙이면 다운로드 버튼에 연결합니다. 이 옵션도 입력 해시와 기존 XML을 다시 확인합니다. 입력이 바뀌면 새 출력 폴더를 사용합니다. 피아노 샘플·WAV 내보내기·코드/로마자 전환은 기존 감상 화면을 재사용합니다. 로마자 전환은 화면에 적용되며 다운로드 원본은 코드 심벌입니다.

## 2026-11-10 청취 초안

입력은 앞서 사용자가 고른 4/4 m5입니다. A는 기존 16마디 authored blueprint의 첫 8마디 선율, B는 이를 데이터 관찰을 참고해 작성한 수정안입니다. 과거 거절된 P2 프레이즈를 사용자 선택으로 기록하지 않았습니다.

- 1–2마디 보존. 변경 마디는 3·6·7.
- 두 버전 C장조, 4/4, 4분음표 100. 오른손 쉼 각각 5박. 페달 없음.
- Mozart K.265: 이웃음 왕복이 주제 0/14, 제1변주 10/49개의 연속 유음 3음 창에서 관찰되어, B의 3마디에 C 주변 장식을 작성했습니다. 원곡의 음열·전체 음 밀도를 복사하지 않았습니다.
- Mozart K.25: 주제 공격점 27개가 변주에도 있고, 그중 24개에서 음고류가 같았습니다. B의 6마디는 입력 모티프의 시작 쉼과 리듬 윤곽을 재현합니다. 7마디의 B→C 종지 접근은 작곡자의 선택이며 자료에서 학습했다고 주장하지 않습니다.
- 공통 왼손은 기존 musicomp retrieval 결과의 1–7마디입니다. 8마디에는 3박의 으뜸화음과 1박 쉼을 직접 작성해 양쪽에 같은 마침을 붙였습니다.

최종 로컬 결과: `K:\MusicGeneration\motif-development\output\comparison-v003`.
감상: <http://127.0.0.1:8795/index.html>. 로컬 서버가 실행 중일 때 사용할 수 있습니다.
아직 사용자의 A/B 청취 판단은 받지 않았습니다. 다음 단계는 선택된 발전 방향으로 16–32마디의 구조와 상세 화성 계획을 작성하는 것입니다.
