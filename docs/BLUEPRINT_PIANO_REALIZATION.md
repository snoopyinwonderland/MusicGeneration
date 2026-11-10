# 모티프 발전곡의 피아노 실현 · 선택 기능

MusicGeneration은 대화에서 작성한 모티프 발전·선율·화성·조성·형식을 악보로 만듭니다. `blueprint_solo`는 같은 선율과 화성 설계에 별도로 작성한 피아노 반주를 붙입니다. `--corpus-accompaniment`를 켜면 기존 musicomp의 반주 검색·밀도 모델을 수정 없이 사용합니다. 자동 작곡가 스타일 변환이나 새로운 모델 학습은 아닙니다.

## 입력과 실행

작업 폴더에 `motif.json`, `development.json`, `realization.json`을 둡니다. 앞의 두 파일은 기존 [발전 설계](MOTIF_HARMONY_BLUEPRINT.md) 형식입니다. 실현안은 아래 구조입니다.

```json
{
  "format": "musicanote-piano-realization",
  "version": 1,
  "score": {},
  "feedback": {"user_text": "실제 청취 의견 원문", "decision": "작성자의 결정"},
  "preserve": {"source": "이전 피아노.musicxml", "bars": 8}
}
```

`score`에는 기존 piece의 motifs/blocks/expression 악보를 넣습니다. 주선율·국소 조성은 발전 설계와 같아야 합니다. 일반 반주 화음의 시점·구성음·베이스도 설계와 맞아야 합니다. 증6화음처럼 일반 코드 심벌로 표현하기 어려운 구간은 음표를 직접 작성하며, 화성 계약은 발전 설계에 남깁니다. `preserve`는 선택 필드이며 지정하면 이전 악보의 처음 N마디 양손 음표·철자·음가·쉼·아티큘레이션을 보호합니다. 현재 재읽기 API가 반환하지 않는 슬러까지 보존 인증하는 것은 아닙니다.

```powershell
$env:MUSICOMP_ROOT = 'K:\Music Composition'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'K:\Music Analysis\.venv\Scripts\python.exe' -B -m musigen.blueprint_solo --work output/piece-input --out output/piece-v002 --corpus-accompaniment
```

출력은 빈 폴더여야 합니다. 반주 검색은 명시한 반주 유형 안에서만 이루어지며 직접 쓴 왼손은 보존됩니다. 실제 선택한 결과는 `solo_score.json`, 출처·분모·해시는 `accompaniment_report.json`에 고정합니다. 기존 생성 명령의 기본값을 바꾸지 않습니다.

## 두 악보와 화성 정보

- `melody_harmony.musicxml`: 같은 주선율과 모든 구성음을 담은 화성 요약 악보.
- `piano_solo.musicxml`: 실제 반주 음표와 명시적으로 작성한 표현을 포함한 연주 악보.
- `harmony.json`: 화성의 시점·길이·국소 조성·전체 구성음·베이스·전위·기능·종지 의도·배치.
- `performed_harmony.json`: 각 화성 구간과 겹치는 실제 왼손 음표·출처·생략음. 구간에 포함된 음들의 집합이며 모두 동시에 울린다는 뜻은 아닙니다.
- `result.json`, 두 `*_checks.json`: XML 재읽기·보존·프레이즈 관찰·음악 검사 결과. 자동 검사와 청취 판단은 구별합니다.

`index.html`은 두 감상 페이지와 상세 화성 표를 연결합니다. 피아노 샘플, 코드 심벌/로마자 전환, MusicXML 받기를 제공합니다. WAV와 샘플 출처 문서는 각각 버튼으로 받습니다. 연속 다운로드가 앞 파일을 대체하는 내장 브라우저 문제를 피하기 위해 한 번의 클릭에 파일 하나를 저장합니다.

PDF는 별도 렌더링하여 `melody_harmony.pdf`, `piano_solo.pdf`로 놓습니다. 그다음 같은 명령에 `--pages-only`를 붙이면 PDF 버튼을 연결합니다. 입력 해시와 고정한 음표를 다시 확인하며, 자료 검색을 다시 수행하지 않습니다. 다운로드 원본은 코드 심벌이고 로마자 전환은 화면 설정입니다.

## 2026-11-11 초안

「작은 발걸음 · 돌아오는 길」: 24마디, 4/4, C장조, ♩=100, 약 58초. 직전 비교 B의 첫 8마디를 보존하고 A단조 대조부, 증6화음 해결, 주제 재현, 부속딸림화음, 차용 iv와 마지막 종지를 작성했습니다. 페달은 없습니다.

사용자 의견은 “무난한 편이네요. 더 진행해 보죠.”입니다. B를 확장한 것은 작성자의 결정이며 사용자가 B를 골랐다고 기록하지 않습니다. 작곡가 스타일 학습 완료나 모차르트풍 검증 결과라고 부르지 않습니다.

입력과 모든 산출물은 `K:\MusicGeneration\motif-piece\output` 아래에만 보관합니다. 감상 주소: <http://127.0.0.1:8796/index.html>. 서버가 실행 중일 때 사용할 수 있습니다.
