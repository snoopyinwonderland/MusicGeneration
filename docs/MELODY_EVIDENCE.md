# 주선율 자료 관찰과 반복·유사도 검사의 범위

이번 기능은 선택 실행하는 로컬 조사다. 생성 기본값, 기존 학습 계수, 자동 프레이즈 경계 설정은 바꾸지 않는다. 자료의 음표를 새 곡에 이어 붙이거나 새 신경망을 학습한 작업도 아니다. 반복은 주제 재현에 사용할 수 있으며, 검사 수치는 삭제·감점·탈락 기준이 아니다.

## 자료를 어떻게 읽는가

`melody_inventory`는 기존 `corpus_catalog`의 자료 루트를 조사하고, 명시적으로 전달한 KYSing 원본 MIDI·리드시트 경로를 추가한다. 파일 수는 작품 수가 아니다. 압축 자료는 컨테이너로 목록에 남기며 임의로 풀지 않는다. 인벤토리는 모든 디스크를 검색했다는 뜻도 아니다.

`melody_evidence`는 지원하는 MusicXML/MXL, SMF MIDI/KAR, 단일 정적 **kern 음표 성부를 읽는다. AI Hub와 권한 미확인 국악 자료, 이미 원본을 선택한 파생 거울 폴더, POP909의 대체 편곡 폴더는 이유를 기록하고 제외한다. 지원하지 않는 기보·오디오·주석·모델 자료는 목록에 남는다. 모든 파일을 성공적으로 선율화했다고 주장하지 않는다.

| 역할 | 근거와 제한 |
|---|---|
| documented_melody | KYSing S1/channel 4, POP909 MELODY, MTC/ESSEN 명시 선율, Weimar 독주 전사처럼 데이터 제작자가 정한 역할 |
| named_melody | 파트·트랙 이름에 melody/vocal/soprano/tenor 등이 명시됨. 합창의 한 성부일 수 있으며 유일한 주선율 보증이 아님 |
| lyric_voice | MusicXML에서 가사 요소가 8개 이상 붙은 성부. 기보 제작자가 가사 요소를 다른 문자에 쓴 경우도 있어 가창 주선율 정답으로 인증하지 않음 |
| single_line_score | 유일한 유음 성부 또는 단일 정적 kern 음표 성부 |
| unknown_voice | 나머지 성부. 최고음을 골라 주선율로 승격하지 않음 |

동시 시작 화음이 있는 성부는 최상음을 따내지 않고 제외한다. 최소 8발음, 양의 길이를 요구한다. MusicXML 붙임줄은 연속 시점이 확인될 때 합치며, 불연속 붙임줄·잘못된 커서 등은 파일별 오류로 남긴다. 장식음·미분음은 계수와 제외 이유를 기록한다. XML은 기보음·기보된 반복 순서, MIDI는 실제 tick과 겹침을 유지하므로 둘을 무조건 같은 시간 표현으로 취급하지 않는다.

MTC는 `duration_frac`와 `IOI_frac`의 4분음표 단위를 사용한다. 6/8의 `beatinsong`을 4분음표로 오독하지 않는다. Weimar의 onset/duration은 **초**로 보존하고 지문에도 시간 단위를 구별한다. 가사 본문은 새 분석 결과에 복사하지 않는다. MTC의 구절 인덱스도 이번 관찰의 사람 정답으로 임의 사용하지 않는다.

이번 가사 활용은 성부 식별 근거와 tick 위치 읽기까지다. 가사의 정서를 해석해 선율·화성에 연결하는 모델은 학습하지 않았다. 해당 단계에는 별도의 정서 주석과 검증이 필요하다.

## 중복과 분모

1. 동일 바이트 SHA-256 파일은 다시 음악 사건으로 세지 않는다. 이미 성공적으로 읽은 바이트 해시만 빠른 건너뛰기에 사용한다.
2. 전체 선율의 시작 시각·절대 음높이를 제거하고 정확한 음가를 유지한 지문으로 중복 성부를 합친다. 같은 선율의 이조 판본은 합쳐질 수 있으나 리듬이 달라진 판본은 별도로 남는다.
3. 여러 데이터베이스의 관찰 집계에서는 명시 역할을 미확정 중복보다 우선한다. 같은 역할 안에서는 전달한 데이터베이스 순서를 따른다.
4. 파일, 데이터베이스 레코드, 성부, 음 사건, 음정 쌍을 별도 분모로 보고한다. 동일 작품의 모든 편곡·변주·연주를 작품 단위로 완전히 통합한 것은 아니다.

읽는 중 파일 크기·수정시각이 바뀌면 거절한다. 중단 재개는 이미 처리한 경로를 건너뛴다. **원본이 바뀐 뒤의 재조사에는 새 출력 폴더를 사용한다.** 기존 DB가 외부 변경을 실시간 추적하는 서비스는 아니다.

## 관찰 수치의 의미

- step_pairs: 0을 제외한 1–2반음 진행. 반복음은 별도 계수다.
- rest_gaps: 앞 음의 끝과 다음 음의 시작 사이에 양의 간격이 있는 음정 쌍. 연주 MIDI의 작은 건반 이탈 간격도 포함하므로 곧바로 ‘프레이즈 쉼’으로 해석하지 않는다.
- leap_reversal: 4반음보다 큰 도약 뒤 다음 음정이 반대 방향인 수 / 다음 음정이 있는 도약 수.
- climax_position: 최고음의 첫 출현 위치. 반복되는 고음이나 정서적 절정의 인식률이 아니다.

음가 히스토그램·음역·겹침 등도 직접 관찰한다. POP909·Weimar의 연주 간격과 기보 그리드인 KYSing의 간격을 같은 호흡 통계로 비교하지 않는다. 자동 경계 도구의 과거 P3 실패를 이 수치로 통과 처리하지 않는다.

차트의 지역·시기·집계 방식을 유지한 소규모 연결 표본은 [CHART_MELODY_COHORT.md](CHART_MELODY_COHORT.md)에 있다. 제목·가수/작곡자·실제 악보 성부를 확인한 항목만 쓴다. 클래식 투표 상위 작품의 주선율 연결은 미확정이며, 일반 클래식 성부 관찰과 별개다. 인기의 원인이나 음악 품질을 추정하는 대조 실험은 하지 않았다.

## 반복·유사도 검사

`melody_line_audit`는 악보를 변경하지 않는다.

- 곡 안: 실제 마디에 맞춘 2·4·8마디 창의 같은 음·리듬 및 단순 이조, 그리고 16음의 한 음 변경 수준 근접 반복을 보고한다. 자동으로 추론한 프레이즈가 아니다. 최소 4발음이 있는 마디 창을 검사하며 긴 단일 유지음은 별도 음악적 판단 대상이다.
- 외부 자료: 2마디 이상에 걸친 연속 12음의 음정·음가·발음 간격 일치, 연속 16음의 한 음높이 변경과 시간 차이 12% 이내 후보를 찾는다. 이조와 일정한 배율의 빠르기 변화는 허용한다.
- 16음 검사는 세 개의 5음정 씨앗으로 후보를 찾고 전체 음높이·길이·발음 간격을 재확인한다. 출력 예시 개수와 전체 일치 창 수를 구별한다.
- 음 삽입·삭제, 임의 장식, 다른 성부 분리, 녹음의 음색·가사, 모든 종류의 유사성은 검출 범위 밖이다. 12음보다 짧은 공통 음형을 배제하는 검사도 아니다.

반복 0회가 좋은 곡의 조건은 아니다. 작성자가 재현의 위치·역할·앞뒤 문장·화성·반주를 함께 검토한다. 외부 일치 후보도 즉시 표절 판정으로 바꾸지 않는다. 어떤 결과도 전 세계 음악과의 독창성이나 법적 권리를 보증하지 않는다.

## 실행

원본은 읽기 전용이며 DB·가사 원문 없는 관찰·생성 악보는 Git 제외 `output/`에 둔다. KYSing 사용은 Composition 개발기록 #175에 남은 사용자 허용 범위의 로컬 분석이다.

```powershell
$env:MUSICOMP_ROOT='K:\Music Composition'
$env:PYTHONUTF8='1'
$py='K:\Music Analysis\.venv\Scripts\python.exe'
& $py -m musigen.melody_inventory --out output/melody-data --kysing-midi-root 'Q:\KY Data\MIDI\KYSing_MIDI' --kysing-leadsheets-root 'Q:\KY Data\Leadsheets'
& $py -m musigen.melody_evidence --out output/melody-data --workers 8
& $py -m musigen.melody_annotated --out output/annotated-data --mtc 'K:\Music Composition\data\external\mtc' --weimar 'K:\MusicSearch\data\jazz-corpora\weimar-jazz-database\wjazzd.db'
& $py -m musigen.melody_profile --database output/melody-data/melodies.sqlite3 --database output/annotated-data/melodies.sqlite3 --out output/melody-observations.json
& $py -m musigen.melody_line_audit --queries output/five-studies/queries.json --database output/melody-data/melodies.sqlite3 --database output/annotated-data/melodies.sqlite3 --database output/previous-data/melodies.sqlite3 --out output/five-studies/melody-audit.json --workers 8
```

`--limit`는 명시적 부분 실행이다. 완료 여부는 `melody-coverage.json`의 `remaining_eligible`로 확인한다. 진행 중의 과거 완료 보고서를 최신 전체 보고서로 오인하지 않는다.

유사도 검사의 `--workers`는 비교 배치의 처리 수만 바꾼다. 읽기 트랜잭션의 파일·성부 수와 질의 지문을 기록하며, 예시 순서와 일치 창 수는 단일 프로세스 실행과 같아야 한다. 원음표 DB는 로컬에 두고 웹에는 집계·검사 보고서만 전달한다.
