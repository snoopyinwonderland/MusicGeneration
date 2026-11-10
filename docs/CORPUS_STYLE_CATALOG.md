# 작곡 참고용 전체 자료 목록과 스타일 관찰

사용자 요청: utf8의 다른 작곡가, MIDI, 대중음악과 기억하지 못한 자료까지 찾아 모티프 발전 작곡에 참고한다. 2026-11-10 꾸러미는 **원천 목록·내용 검사·마디/성부 관찰·분류 메타데이터**를 만든다. 신경망 작곡 모델을 새로 학습하거나 기존 출력의 기본 설정을 바꾼 것은 아니다.

## 실행

```powershell
$env:MUSICOMP_ROOT = 'K:\Music Composition'
$env:PYTHONIOENCODING = 'utf-8'
& 'K:\Music Analysis\.venv\Scripts\python.exe' -m musigen.corpus_catalog inventory --out output/corpus
& 'K:\Music Analysis\.venv\Scripts\python.exe' -m musigen.corpus_catalog metadata --out output/corpus
& 'K:\Music Analysis\.venv\Scripts\python.exe' -m musigen.corpus_catalog motif-map --out output/corpus
& 'K:\Music Analysis\.venv\Scripts\python.exe' -m musigen.corpus_catalog observe --out output/corpus --midi-limit 64
& 'K:\Music Analysis\.venv\Scripts\python.exe' -m musigen.corpus_catalog summary --out output/corpus
& 'K:\Music Analysis\.venv\Scripts\python.exe' -m musigen.corpus_catalog query --out output/corpus --composer handel
& 'K:\Music Analysis\.venv\Scripts\python.exe' -m musigen.corpus_catalog query --out output/corpus --era classical --region Vienna --active-at 1785
```

`inventory`는 명시된 음악 자료 루트의 모든 파일명을 읽는다. 모든 디스크·개인 파일을 검색하는 도구가 아니다. `rg --null`로 줄바꿈이 있는 파일명도 보존한다. `.git`, node_modules와 런타임 의존성은 자료로 합치지 않는다. 압축본은 별도 목록이며 압축을 풀어 원본과 중복 합산하지 않는다. 발견된 파일 수는 곡 수가 아니다. `.xml`에는 MusicXML 외 문서가 있을 수 있다.

`observe`는 utf8와 Mozart/Beethoven/Chopin 폴더의 MusicXML 전체를 시도한다. 다른 코퍼스는 MIDI 경로의 SHA 정렬로 코퍼스당 최대 64개를 검사한다. 이는 내용 표본 검사이며 MIDI 전체 학습이 아니다. `--midi-limit 0`은 선택된 자료 루트의 MIDI 전수를 검사하므로 큰 작업이다. KY·AI Hub 관련 항목은 현행 저장소 정책에 따라 위치·수량만 조사한다.

## 저장하는 정보

| 산출물 (모두 output 아래) | 의미 |
|---|---|
| inventory.json, files.jsonl.gz | 실제 경로·파일 형식·자료 단위와 README/라이선스 위치 |
| metadata-summary.json, work-contexts.jsonl.gz | YCACL 원 연대·국가·장르·편성 필드. 로컬 악보와 자동 연결하지 않음 |
| giant-midi-contexts.jsonl.gz | GiantMIDI의 실제 로컬 MIDI와 audio_name 완전일치한 원 작곡가·생몰년·국가 메타데이터. 생애 정보 개별 검증 전 |
| native-performance-splits.json | MAESTRO의 원 train/validation/test. `year`는 연주 녹음 연도 |
| motif-development-map.json | TAVERN의 작품 → 주제/변주 → 프레이즈 → 주석자별 경로·SHA, BPS 32악장의 실제 모티프 주석과 원 음표 주소. 변주 간 음별 정렬 인증은 아님 |
| observations.jsonl | 읽은 파일 SHA, 중복 대응, 읽기 실패, 원 작곡가·파트·권리 문구, MIDI 트랙/채널·음역·셈여림·페달 이벤트 수 |
| bars.jsonl.gz | 파트·마디·보표·성부별 음높이 철자, 정확한 유리수 onset/duration, 쉼·타이·장식음, 명시적 화성 원문 |
| style-profiles.json | 작곡가 이름별 박자·음가·단선율 성부 내 음정 분포와 분모 |
| coverage.json | 각 자료의 전수/표본/성공/실패/바이트 중복 수 |
| summary.json, summary.md, midi-profiles.json | 자료별·작곡가별 집계와 MIDI 표본 관찰. 표본을 전체 코퍼스의 추정치로 확대하지 않음 |

마디 순번은 0부터이며 인쇄 번호를 별도 보존한다. 같은 파트의 backup/forward를 따라 좌표를 읽는다. 타이 stop은 새로운 attack으로 세지 않으며 장식음은 보존하되 시각을 지어내지 않는다. 못갖춘마디를 온마디로 채우지 않는다. 부정확한 cursor·division은 제외 사유로 기록한다. 반복은 펼치지 않는다.

XML 음높이는 **기보음**이다. 이조 악기의 실음으로 변환하지 않았으므로 관현악 전체의 울리는 화음이나 실음 음역을 이 값에서 바로 계산하면 안 된다. `midi` 필드도 XML에서는 기보음을 수치화한 값이고, MIDI 파일에서 직접 읽은 소리 음높이와 의미가 다르다.

MIDI는 SMF 0/1·PPQ를 읽고 SMPTE/format2는 거부한다. 트랙·채널·타이밍·드럼·페달을 구분하며 missing meter에 4/4를 넣지 않는다. 같은 음의 겹침·미완료 음·orphan note-off는 경고를 남긴다. 페달 때문에 실제로 더 울린 길이를 기보 음가로 바꾸지 않는다. MIDI나 다성부 악보의 최고음을 주선율이라고 정하지 않는다. 가사 이벤트 수만 세며 본문을 공개 산출물에 옮기지 않는다.

## 작곡가·시대·지역

`musigen/data/composer_context.json`은 확인한 생몰년·출생지·활동 지역·일부 활동 구간과 근거 URL을 담는다. 11명의 기본 정보가 있으며 나머지 작곡가도 이름별 관찰 통계는 남는다. J.S. Bach와 C.P.E. Bach처럼 성이 같은 작곡가를 합치지 않는다. 파일명 전체 이름과 XML 작곡가가 서로 다르면 conflict로 남긴다. 파일명에만 있는 이름은 그 근거를 명시하며 작곡가 저작 인증이 아니다.

GiantMIDI의 metadata.csv는 실제로 탭 구분이며, 143,572행의 검색 후보 목록을 다운로드된 MIDI 수와 혼동하면 안 된다. 로컬 10,854개 중 10,754개가 audio_name으로 완전 일치하며, 그 안에 작곡가 이름 쌍 2,777개가 있다. 100개 미매칭을 임의 연결하지 않는다. 원 생몰년/국가 항목을 함께 보존하지만 별도로 확인한 11명 생애 정보와 같은 검증 수준으로 표시하지 않는다. metadata의 audio_name에는 확장자가 없어 `Op.27` 같은 점을 파일 확장자로 잘라 버리지 않는다.

바로크·고전·낭만·초기 현대는 검색을 위한 편집 태그이며 한 작곡가가 둘 이상에 속할 수 있다. 출생 국가로 음악적 정서를 정하지 않는다. 국적, 출생지, 활동 지역, 작품의 작곡 연도는 서로 대체하지 않는다. `active-at`는 확인된 활동 구간에만 적용하고 생몰년으로 빈칸을 채우지 않는다. 작품 연도가 없으면 그대로 비운다. YCACL `Nationality`와 `Range`도 원 필드 이름을 보존한다.

예를 들어 헨델의 출생지는 Halle이고 런던에서 활동한 이력이 있으므로 둘을 별도로 검색할 수 있어야 한다. 생애 정보의 근거는 [Handel Hendrix House](https://handelhendrix.org/discover/learn-about-handel)이며, 이 문서의 시대 태그는 시스템의 편집 분류다. 파일 자체의 장르·편성과 실제 음형을 함께 보아야 한다.

## 작곡에 연결할 자료의 역할

| 목적 | 발견한 자료 | 적용 전 확인 |
|---|---|---|
| 주제 → 변주·반복·대조 | TAVERN, BPS motif, JKUPDD, MTC/ESSEN | 주제와 변주의 대응, 마디 시작·프레이즈 경계. JKUPDD MIDI는 검사 편의용으로 시작 위치가 부정확할 수 있어 원 CSV/Lisp 우선 |
| 클래시컬 기능 화성·종지·전조 | DCML, When in Rome, TAVERN, ChoCo의 사람 주석 | 겹치는 원 코퍼스 중복 제거, 명시적 국소 조성·로마자·종지 근거. 단순 음집합을 기능 정답으로 만들지 않음 |
| 팝 선율·왼손 반주 | 기존 924곡 train 피아노 자료, POP909, Wikifonia/OpenEWLD, Hooktheory | POP909의 MELODY/BRIDGE/PIANO 역할, 버전 중복, 자동 라벨과 사람 주석 구분 |
| 가사와 선율의 관계 | 중국어 MIDI–가사 250곡, Cantopop 105곡 표기 자료, 노래방 자료 | 가사·음절 정렬과 언어, 출처. 정서 정답 라벨은 확인되지 않았고 제목만으로 만들지 않음 |
| 재즈·대중음악 표현 확대 | Weimar, Jazz Harmony Treebank, clean MIDI/Lakh, 128k archive, 게임·지역별 MIDI | 트랙 역할·장르·원곡 ID가 없는 MIDI는 별도 유지. 재즈/게임이라는 폴더 이름이 모든 음의 스타일 정답은 아님 |
| 피아노 연주 표현 | MAESTRO, ASAP, GiantMIDI | 악보와 연주 좌표 분리. GiantMIDI는 자동 전사이며 MAESTRO/ASAP은 원 분할·정렬 보존 |
| 폭넓은 시대·편성 | utf8, PDMX, Mutopia, OpenScore, YCAC/YCACL, Humdrum/MEI/기타 악보 | 피아노·성악·관현악 분리, 판본 중복·파트 역할·지원 형식 확인 |

### 이미 있는 통계와 새 자료를 구분

musicomp의 patterns/songs.json에는 train 924 / holdout 234가 있다. pacing_model.json의 학습 이력은 250곡·22,735마디, motif_salience.json은 BPS 32악장·발견한 동기군 596개다. 새 모델을 학습한 숫자가 아니다. pop_melody.json은 기존 사람 화음 생성 통계로 연결되어 있다. phrase_end_model.json에는 KY 가사 줄 끝 기반이라는 출처가 있어 다른 새 자료처럼 무조건 섞으면 안 된다.

기존 Analysis의 human-chord-generation, DCML/classical accompaniment, string-ensemble, NCT 결과도 재사용 후보로 찾았다. 전수 음표/화성 주석, 적용 가능한 희소 마디 라이브러리, 실험 모델, 평가 보고서는 서로 다른 종류이며 보고서를 학습 예제로 취급하지 않는다.

## 이번 통계를 사용하는 범위

지금 가능한 것은 대화에서 작곡 설계를 세울 때 작곡가별 실제 음가·쉼·음정·박자 분포와 자료 출처를 조회하는 것이다. 여러 악기가 섞인 원 코퍼스의 pooled 평균을 피아노 솔로의 목표값으로 강제하지 않는다. 바이트 중복은 분석 입력 사이에서 제거했지만 판본·이조·악장·편곡의 work-ID까지 완전히 해결한 것은 아니다.

모든 새 관찰은 `generation_eligible: false` / `inspection_only_unpartitioned`다. 아직 train/eval을 확정하지 않은 원천을 검색 편곡기나 모델 학습에 자동 투입하지 않는다. 기존 native split·동일 작품/판본 연결·권리 구분·역할 검증을 마친 자료부터 별도 opt-in으로 전환한다. 코드·저장소 라이선스가 모든 악곡의 권리를 대신한다고 간주하지 않는다. 원 악보·음형 행·가사는 Git에 넣지 않는다.

다음 연결의 우선순위는 **주제–변주 대응 → 2/4/8마디 연결과 종지 → 국소 조성/전조 → 왼손 반주 → 연주 표현**이다. 양만 늘려 기존에 지적받은 단조로움이 해결됐다고 보고하지 않는다. 사용자 모티프의 보존과 새 프레이즈의 청취 검수를 별도로 수행해야 한다.

2026-11-11에는 [2·4·8마디 시각 참조](PHRASE_CONTEXT_LIBRARY.md)를 별도 선택 기능으로 추가했다. 지정 TAVERN 40프레이즈 중 11개에서 악보와 주석의 시각이 일치했고, 그 안의 겹치는 온마디 창 77개를 탐색한다. 원 화성 라벨·분석자 차이·끝 음가를 보존하며 종지 종류나 전조를 추정하지 않는다. 다음 자료 단계는 명시적 국소 조성과 전조 주석 검증이다.
