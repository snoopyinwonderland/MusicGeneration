# 검수 요청: 국소 조성 원 악보 시각의 독립 검증

- 브랜치 `codex/tonal-timing-audit`, 작업 트리 `K:/MusicGeneration/tonal-timing`.
- origin/main `72ca816`에서 시작해 선행 12개 변경을 cherry-pick했습니다. 이번 변경 직전 HEAD `62193f1`입니다. main과 원 코퍼스는 수정하지 않았습니다.
- 사용자 승인 범위: 전조 자료의 남은 검증과 여러 마디 반주 연결 설계. 이 꾸러미는 첫 번째인 원 악보 검증입니다.

## 무엇을 왜 바꿨는가

기존 검사는 TSV끼리의 시각과 XML의 마디/보표/성부별 라벨만 확인했습니다. 이제 `musigen/mscx_timing.py`의 `parse`, `audit`가 ms3를 호출하지 않고 MuseScore 3 XML을 독립적으로 읽어 음표의 시각·분수 음가·MIDI·철자·장식음 종류, 마디 시계, 화성 라벨의 정확한 시각을 대조합니다. 성부·못갖춘마디·점음표·잇단음표·location 이동을 처리하며 알 수 없는 시간 구조는 거부합니다. 붙임줄 음표는 기보된 조각별로 비교하고 반복은 펼치지 않습니다.

`musigen/tonal_reference.py`에 선택 `--verify-score-timing`을 추가했습니다. 통과한 결과만 새 참조 라이브러리에 들어가며 기존 파일을 덮어쓰지 않습니다. `tools/audit_tonal_timing.py`는 기존 라이브러리에서 제외된 작품까지 원 파일 해시를 확인하여 독립 검사하는 읽기 전용 명령입니다. `musigen/tonal_plan.py`의 근거 화면은 검증 수준에 맞는 설명과 전체 원 라벨을 표시합니다.

## 이전 두 제외 사례의 원인

원자료 오류로 확인된 것이 아니라 **기존 검사에서 대안 해석 열을 빠뜨린 것**입니다. Beethoven 01-1의 네 주석과 Chopin op.30-2의 한 주석은 XML의 `기본-대안` 문자열을 TSV의 `label`, `alt_label`에 나눠 저장하고 있었습니다. 두 열을 정확히 결합하여 원 문자열·시각과 대조하고 대안을 내보내기에 보존합니다. 대안을 기본 해석에 섞거나 추가 학습 사례로 세지 않습니다.

또 Chopin op.30-2에는 `.Fr6/III`처럼 다른 조성 문맥에 놓인 프랑스 증6화음이 있습니다. ms3는 이를 확장하며 내부 `/V`를 덧붙입니다. 원 문맥과 확장값을 구별해 보존하고, 이 증6화음을 일반 세컨더리 화음 건수에 넣지 않습니다. 근거: [ms3 원 라벨 확장 코드](https://ms3.readthedocs.io/en/stable/_modules/ms3/expand_dcml.html)의 대안 분리와 `replace_special`의 목적 병합. 작품별 예외나 인식 계수 변경은 없습니다.

## 결과와 재현

고정 6개 악장 모두 **8,121개 기보 음표·1,123개 화성 라벨·1,104개 보표별 마디**의 정확 대조가 통과했습니다. 1,104개는 양손 보표를 따로 센 수입니다. 장식음도 0 길이로 대조하며 실제 연주 음가를 추정하지 않습니다.

새 라이브러리의 국소 조성 변화는 17곳, 일반 슬래시 으뜸화는 159곳입니다. 이전 10/104에서 증가한 것은 새 두 악장을 포함했기 때문이며 같은 작품의 사건 수입니다. 원 파일 해시 검사 36회, music21 으뜸음 철자 교차 검사 30종 통과. `output/library-v002.json` SHA-256은 `2dfac1ede5f7d17240d4ea55f7e3d07fa5a8b96ddb956310762cf8c35c26d822`입니다.

```powershell
$env:MUSICOMP_ROOT = 'K:\Music Composition'
$py = 'K:\Music Analysis\.venv\Scripts\python.exe'
& $py tools/audit_tonal_timing.py --root 'K:\MusicSearch\data\classical-corpora\dcmlab' --library '../tonal-development/output/tonal-v005/library.json' --out output/audit-new.json
& $py -m musigen.tonal_reference --root 'K:\MusicSearch\data\classical-corpora\dcmlab' --allow-dcml --verify-score-timing --works mozart-sonatas/K279-1 mozart-sonatas/K279-2 beethoven-sonatas/01-1 beethoven-sonatas/01-2 chopin-mazurkas/BI105-2op30-2 chopin-mazurkas/BI105-3op30-3 --out output/library-new.json
```

`tests/test_mscx_timing.py` 8개와 기존 tonal reference에 상대 증6화음 검사 1개를 추가했습니다. 전체 193개 테스트 통과. 같은 마디 안의 잘못된 화성 시각, 음표 누락/중복/다른 철자/음가, 잘못된 대안, 미지원 구조를 거부하는 회귀 검사를 포함합니다.

음표나 새 곡을 수정한 꾸러미가 아니므로 청취 전후판은 없습니다. 기존 [조성 연결 시험곡](http://127.0.0.1:8802/index.html)은 그대로이며, 다음 반주 꾸러미에서 같은 선율·화성의 비교를 만듭니다.

## 위험과 남은 범위

제한된 MuseScore 3 기보 파서입니다. 실연 시각, 이조 악기, 모든 MuseScore 버전과 구조, 반복 전개를 지원한다는 뜻이 아닙니다. 대안 해석은 원문 보존이며 별도의 조성 상태 경로로 분석하지 않습니다. 전조·종지의 청취 타당성은 여전히 별도 검수입니다. 원 데이터와 출력은 Git에서 제외하고 DCML 선택·비상업 조건을 유지합니다. P3/P4 중단과 자동 스타일 생성 보류는 유지합니다.
