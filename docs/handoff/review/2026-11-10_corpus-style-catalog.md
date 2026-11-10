# 검수 요청: 전체 음악 자료 발견·스타일 관찰

- 브랜치: `codex/corpus-style-catalog`
- worktree: `K:\MusicGeneration\corpus-style`
- 기준: 최신 fetch의 `origin/main` 72ca816. 모티프 입력/기능 화성 꾸러미 `codex/motif-studio-harmony` b72bd2d와 독립적으로 검수할 수 있는 조사 모듈이다.
- 저장소: https://github.com/snoopyinwonderland/MusicGeneration

## 문제와 결과

사용자는 Mozart/Beethoven/Chopin뿐 아니라 utf8의 다른 작곡가, MIDI·대중음악·누락된 자료 전체를 참고하고 시대·활동 시기·출신지에 따른 분류를 요청했다. 기존 목록만 반복하지 않고 실제 파일 수를 다시 집계하고, utf8 악보 전체의 마디/성부 관찰과 MIDI 코퍼스별 표본 검사를 수행했다. 기존 생성기 기본값·원악보·Music Analysis/Composition 코드는 변경하지 않았다.

새 학습 모델 또는 자동 스타일 작곡 완료를 의미하지 않는다. 새 원천을 기본 학습/생성에 합치지 않으며 관찰 행은 `generation_eligible: false`다. 대화에서 참고할 자료의 내용·분모·불확실성을 확보한 꾸러미다.

## 변경한 파일과 함수

| 파일 | 내용 |
|---|---|
| `musigen/corpus_catalog.py` | discover_sources/source_files/inventory, observe, metadata, motif_map, query, summarize 명령 |
| `musigen/corpus_features.py` | XML 마디/성부와 MIDI track/channel/time 관찰. 추정 melody/harmony를 만들지 않음 |
| `musigen/data/composer_context.json` | 11명 생애/활동 정보와 확인 출처. 시대는 편집 태그, 작품 연대와 구별 |
| `tests/test_corpus_catalog.py` | 10개 검사: backup/chord/tie/grace, 잘못된 좌표·XML entity, MIDI running status/채널/손상, 동성 작곡가, 줄바꿈 파일명, 활동 연도 필터, TAVERN 이름 변형 |
| README, `docs/CORPUS_STYLE_CATALOG.md` | 실행·용도·자료별 다음 연결·한계 |

## 실제 읽은 범위

- 음악 자료 루트 **69곳**, 파일 **1,006,486개**. XML/musicxml/mxl 확장자 **388,510개**, MIDI/midi/kar **300,065개**. 이는 고유 작품 수가 아니고 XML 확장자만으로 악보 판정도 하지 않는다. 압축본·변환본·중복 코퍼스를 별도 유지한다.
- 추가로 K 드라이브의 음악 관련 압축본 8개 내부 목록을 확인했다. KYSing 압축본 50,874 XML은 U의 풀린 원본과 합쳐 새 작품 수로 세지 않는다. MUSICALIBRA 앱의 추가 XML 다수는 런타임 폰트/시험 자료라 학습 데이터로 합치지 않았다. 그 조사에서 `.pytest_cache` 읽기 거절도 기록했다.
- utf8 **3,299파일 전수 시도**: 성공 상태 3,231(그중 이미 읽은 바이트와 중복 83), 제외 68. 실제 새로 관찰한 utf8 파일 3,148.
- 원 Mozart/Beethoven/Chopin 208파일도 같은 엄격한 시간 파서로 검사. 총 XML 시도 **3,507**, 중복 제외 내용 분석 **3,334**, XML 제외 **71**, XML 바이트 중복 **102**. 앞선 단순 XML 파싱 207/208과 이 시간/성부 추출 수치는 기준이 다르다.
- MIDI **1,254파일 표본/소규모 전수 시도**, 내용 분석 **1,226**, 제외 **12**, 바이트 중복 **16**. 코퍼스별 최대 64개이며 전체 30만 MIDI를 읽거나 학습했다는 뜻이 아니다. 악보 좌표로 강제 양자화하지 않았다.
- 분석 XML의 **2,478,982 파트 마디 / 2,739,224 성부 마디 / 음 공격 9,031,960개**. 작품 마디와 다른 단위이며 많은 합창/관현악 성부를 포함한다. 이름 그룹 38개(unknown 포함), 그중 11개만 별도 생애 문맥 검증 자료가 있다.
- 파일별 악보 마디 위치 합은 390,636이며 이것도 고유 작품의 마디 수는 아니다. XML 음높이는 기보음으로 실음 이조를 적용하지 않았다. MIDI 내용 검사 1,226파일 중 533에는 음 겹침/미완료 등의 관찰 경고가 있어 곧바로 훈련 정답으로 승격하지 않는다.
- 제외 사유에는 division 없음 53, 음수 backup 4, 빈/잘못된 XML 14, MIDI 포맷/바이트 오류 12가 있다. 파일별 실패·SHA는 observations.jsonl. 원자료를 자동 보정하지 않았다.

## 새로 연결한 참고 자료

- **TAVERN**: Joined 파일 실제 27개 작품 그룹, 주제 95프레이즈, 변주 274그룹·1,015프레이즈. 주석자별 파일은 분리. README의 281변주·1,060프레이즈 소개와 로컬 Joined 관찰은 같지 않으므로 소개 숫자로 덮어쓰지 않는다. 변주 간 음별 정렬 인증은 아니다.
- **BPS**: 32악장, 모티프 주석 4,944행, 원 csv_notes 주소 32개 모두 존재. 기존 motif_salience의 596 발견 동기군과 다른 단위다.
- **POP909**: MIDI 2,898파일 중 canonical 위치 909개. versions를 새 곡으로 세지 않는다.
- **YCACL**: 10,085 메타데이터 행·577 작곡가 표기. 연대·국가·장르·편성 원문 보존. 작품별 XML과 자동 연결하지 않는다.
- **GiantMIDI**: 로컬 MIDI 10,854개. metadata의 143,572 검색 후보 전체를 받은 악보로 간주하지 않는다. audio_name 완전 일치 10,754파일·작곡가 이름 쌍 2,777개. 미매칭 100개 보존. 생몰년/국가는 source claim이며 출생지/활동 시기와 같지 않다.
- **MAESTRO**: 원 분할 train 962 / validation 137 / test 177 보존. year는 녹음 연도다.
- **중국어 MIDI–가사**: 250 MIDI와 250 TXT의 같은 이름 짝 확인. 첫 5 가사 파일에 LRC timestamp 없음. 음절 정렬·정서 라벨은 검증 전이다. 가사 본문을 저장소에 넣지 않는다.
- DCML, When in Rome, Taking Form, ChoCo, OpenScore, ESSEN/MTC, JKUPDD, Weimar/Jazz Harmony Treebank, 기타/지역/게임 MIDI, PDMX, 국악·노래방까지 목록과 README를 확인했다. 기존 사람 화음 통계(3,183 제목, 완전 마디 98,754)와 현악/반주/밀도/프레이즈 결과는 새 학습과 구분해 재사용 후보로 기록했다.

## 검증 및 전후

- 전체 unittest **101개 통과**(기존 91 + 이번 10). `git diff --check` 통과.
- 실제 query `handel`은 헨델 그룹만, `classical + Vienna + 1785`는 확인된 활동 구간이 있는 Mozart만 반환. 다른 작곡가의 생몰년으로 빈 활동 구간을 채우지 않는다.
- 실제 전수 XML 파이프라인과 1,254 MIDI 검사 종료, metadata/motif-map 명령 종료 확인. 전체 바이트·마디 파일의 압축 종료·행수·합계 대조는 `output/corpus/validation.json`에 기록한다.
- 전후 청취 대상 없음: 생성 악보/기본 화성/반주를 바꾸지 않은 데이터 참조 꾸러미다. 통계의 통과를 청취 품질 향상으로 주장하지 않는다.
- 로컬 결과: `K:\MusicGeneration\corpus-style\output\corpus\summary.md`, `style-profiles.json`, `bars.jsonl.gz`, `midi-profiles.json`, `motif-development-map.json` 등. 원 음형·작품별 목록·가사는 Git에 넣지 않는다.

## 위험·남은 범위

파일명 작곡가는 이름 후보이며 저작 인증이 아니다. 바이트 중복 제거는 편곡/판본/work-ID 중복 제거가 아니다. 관현악·성악을 섞은 평균 밀도를 피아노 솔로 목표로 쓰면 안 된다. XML tie stop을 새 attack에서 제외했지만 장식음/타이의 연주 실현·전후 프레이즈 연결·기능 화성 추정은 하지 않는다.

새 자료의 원 native split과 기존 평가곡(work-ID)을 대조하고 역할·라이선스 조건을 확정한 뒤에만 실제 생성용 검색/모델에 opt-in으로 넣어야 한다. KY/AI Hub는 이번에 위치·목록만 조사했다. 기존 phrase_end_model의 KY 유래도 문서화했으며 새 학습에 자동 편입하지 않았다.

주제–변주 대응과 프레이즈 연결, 사람 화성/종지, 반주, 연주 표현 순으로 활용하는 것이 이 자료와 현재 작곡 목표에 맞는다. 이번 검수의 승인과 별도로 실제 새 곡에 적용한 결과는 사용자의 청취를 받아야 한다.
