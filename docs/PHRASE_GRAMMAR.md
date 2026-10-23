# 프레이즈 후보와 기능 문법 (선택 기능)

P1에서 `choose`로 기록한 모티프만 사용합니다. 기존 `piece` 입력과 예시 출력은 유지합니다.

```powershell
python -m musigen phrases <작업 폴더> --count 4
python -m musigen choose <작업 폴더> <phrase-selection.json 또는 p번호>
python -m musigen piece <choose가 출력한 piece_work> --out <결과 폴더>
```

`stage2_phrases/index.html`에서 8마디 후보를 비교합니다. 모티프 선택과 프레이즈 선택은 별개 단계이며, 페이지 위에 박자와 사용한 모티프를 표시합니다. 후보 개수는 `후보 4개`로 쓰며 박자처럼 표시하지 않습니다. 프레이즈 선택은 `selections.jsonl`에 추가되고 `selected_phrase.json`에 보관됩니다. 선택 당시 모티프 기록 ID도 남습니다. 모티프·설계가 바뀌면 프레이즈를 다시 생성해야 합니다.

## 기능 문법

구조 근거: William E. Caplin, *Classical Form* (1998), 3–5장. [저자 설명](https://www.music.mcgill.ca/~caplin/teaching-classical-form.pdf), [출판사 문장형 설명](https://academic.oup.com/book/49159/chapter-abstract/422032516). 짧은 기본 악상을 반복하고 이어짐·종지로 향하는 문장형과, 앞악구·뒷악구를 대조하는 악절형의 기능 구분을 사용합니다. 아래 구체적인 음, 길이, 반주 배치는 이 구현의 **잠정 선택**이며 교과서의 유일한 해법이 아닙니다.

| 유형 | 마디와 기능 | 기본 처리 |
|---|---|---|
| sentence | 1–4 제시 / 5–6 이어짐 / 7–8 종지 | 1마디 모티프+응답으로 2마디 악상, 딸림형 반복, 조각+순차 진행, V–I |
| period | 1–4 앞악구 / 5–8 뒷악구 | 4마디 반종지, 5–6마디에 첫 2마디 정확 반복, 8마디 정격종지 |
| hybrid | 1–4 앞악구 / 5–6 이어짐 / 7–8 종지 | 앞악구 뒤 조각·순차 진행과 정격종지 |
| sentence 변형 | 같은 기능 경계 | 이어짐에서 리듬을 절반으로 축소 |

이어짐 구성 단위는 반 마디로 짧아지고 화성도 반 마디마다 바뀝니다. 제시는 기존 broken, 이어짐은 기존 block을 한 옥타브 안으로 재배치, 종지는 bass 음형을 사용합니다. 악절형은 broken을 유지합니다. 프레이즈 전체에 페달은 없습니다.

```json
{"bars":"1-8","phrase":{
  "type":"sentence","motif":"a","range":[60,81],
  "functions":{"continuation":{"bars":[5,6],"technique":["fragment","sequence:+1"],"harmonic_rhythm":"faster"}},
  "accompaniment":{"presentation":"broken","continuation":"block","cadential":"bass"},
  "overrides":[{"bars":"8","rh":"D5/q C5/h."}]
}}
```

덮어쓰기 마디는 프레이즈 안의 상대 번호 1–8입니다. 기존 블록의 rh/rh2/lh/lh2, chords, dyn, text를 사용할 수 있습니다. `phrase` 블록은 다른 기존 블록과 순서대로 함께 놓을 수 있습니다. 첫 버전은 3/4·4/4, 한 마디 이내 단선율, 8마디 기능 경계를 지원합니다. 기존 모티프 `realise`·`apply`를 사용합니다. 새 직접 재료 `musicanote-motif` JSON도 성부 안에 놓을 수 있습니다.

화성은 기본값 또는 정확한 8마디 목록입니다. `I i IV iv V V7 ii ii° vi VI`와 기존 코드 기호를 받습니다. 마디를 나누려면 `"harmony":["I","I","V","V","IV:2 V:2","IV:2 V:2","V","I"]`처럼 씁니다(4/4 예). 잘못된 길이는 자동 보충하지 않습니다.

## 검사와 한계

`checks.json`의 `phrase_functions`에는 실제 마디별 평균 음높이·음 밀도·화성 변화 수, 종지 화음과 선율 끝음, 악절형의 첫 2마디 반복 검사가 나옵니다. 설계 절정과 평균 음높이 정점의 1마디 이내 여부는 잠정 관찰입니다. 단위 축소는 생성 시 지정한 구성 단위의 길이를 확인하며, 청각적 분절을 자동 판정했다는 뜻이 아닙니다. 이어짐을 덮어쓰면 그 판단을 보류합니다.

선택 후 준비하는 16마디는 같은 프레이즈의 재현에서 반주를 바꾼 기술 연결용 초안입니다. 새로운 대조부를 자동 작곡했다거나 완성도가 검증됐다는 뜻이 아닙니다. 반복·화음 구성음 위주의 진행이 기계적으로 느껴지면 규칙을 계속 추가하지 않고 P3 통계와 P4 시험 결과를 기다립니다. P2·P3·P4는 기본 적용되지 않습니다.
