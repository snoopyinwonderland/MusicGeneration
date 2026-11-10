# 검수 요청: AMT 16개 이어쓰기 진단과 중단 판정

- 브랜치 `codex/amt-continuation-trial`, origin/main `72ca816`에서 별도 작업트리를 만들고 선행 shared-theme 및 AMT 준비 코드를 cherry-pick했습니다. 이번 꾸러미 직전 HEAD `54b9d06`.
- 결과: **16회 생성 완료, 이번 박자·조성 기보 조건 통과 0/16. 계획의 4개 미만 중단 기준에 도달해 종료**. 재시도·다른 모델 시험·조건 완화·기본 적용 없음.
- 입력은 사용자가 거절한 P2 p1–p4가 아닙니다. 이후 수정한 m5 기반 완성곡 「작은 발걸음 · 돌아오는 길」의 1–2마디를 **작곡자가 진단 입력으로 지정**했습니다. 실제 P2 프레이즈 선택을 받은 정식 P4 완료로 표시하지 않습니다.

## 변경

- `musigen/model_trial.py`: 생성 전에 고정하는 프로토콜, 원본 사건에 대한 기보 적합성 검사와 중단 집계. 모델 의존성을 기본 패키지에 추가하지 않음.
- `tools/amt_prepare_input.py`: C장조·4/4·100 BPM의 첫 2마디 선율과 화음, 3–8마디 고정 블록 화음을 정확한 10ms 토큰으로 변환. 입력의 SHA-256와 작곡자 지정 상태 저장.
- `tools/amt_generate_trial.py`: 고정 source revision·모델 revision과 캐시만 이용. 상위 `generate`를 그대로 사용하고 시간·사건 수 제한만 감쌈. MIDI/원본 토큰/검사/소요 시간/메모리 기록.
- `tools/amt_verify_trial.py`: 생성 재실행 없이 첫 2마디 토큰 동일성·16개 결과·집계·아티팩트 지문 검증.
- `tests/test_model_trial.py`: 원본 불변, 허용 오차, 격자/조성/다성 거절, 미완료·빈 후보, 중복 seed와 중단 경계 4개 검사.

## 사전 조건과 해석

seed 0–15, top-p 0.98, CPU 6스레드. 8마디 중 1–2마디는 고정하고 3–8마디를 생성합니다. 1후보당 120초 또는 384사건을 한도로 두었습니다. 16개 모두 시간/사건 한도 전에 생성 루프가 끝났습니다.

기보 조건은 **잠정**입니다: C장조 음계, 16분음표 격자의 시작/길이 ±20ms, 6마디 구간, 매 마디 사건 존재. 추가 직접 악보 조건은 피아노 program 0, C4–C6, 단선율입니다. 허용 오차 안의 사건만 격자에 대응시키며, 실패 후보의 음·성부를 바꾸거나 골라내어 통과시키지 않습니다. 실제 출력 16개 모두 격자·조성에서 이미 탈락했습니다.

AMT는 절대시간 MIDI 사건 모델입니다. 박자표·조표·프레이즈 문법 메타데이터를 직접 받지 않으며, 조건은 고정 음표 문맥과 화음 사건으로 주고 사후 검사합니다. 생성기의 악기/단선율 마스크를 새로 만들지 않았습니다. 따라서 이번 결과는 **현재 사건 모델을 이 프로젝트의 악보 작성 조건에 직접 연결한 시험의 한계**이며, AMT 전체의 음악적 가치나 모든 생성물의 청취 품질 판정이 아닙니다. expressive timing을 기보 격자로 옮기는 문제와 작곡 품질을 구별해야 합니다.

## 실제 측정

| 항목 | 결과 |
|---|---|
| 모델 | stanford-crfm/music-small-800k, 128,103,936 parameters |
| 가중치 revision | fa800530aa1126dd6b58b38f3bdb8fcec9c9d4f5 |
| 코드 revision | af37397922665a0fb8d474d7988b0f3755a38d45 |
| 로딩 | 캐시 전용 1.728초 |
| 생성 | 16회, 합계 927.969초 ≈ 15분 28초 |
| 프로세스 최대 Working Set | 1,273,577,472 bytes ≈ 1.19 GiB, 모델·런타임 포함 |
| 박자·조성 통과 / 직접 악보 통과 | 0/16 / 0/16 |
| 고정 첫 2마디 | 원본 토큰과 16/16 일치 |
| MIDI/원본 토큰 | 16개 모두 보존 |
| 실제 사용자 선택 | 없음 |

중복 가능한 사유별 후보 수: 격자 밖 16, 조성 밖 16, 피아노 외 프로그램 16, 선율 음역 밖 16, 다성 사건 16, 구간 초과 13, 0음가 또는 격자 대응 시 0음가 11, 사건 없는 마디 11. 이 수치를 더해서 탈락 분모로 쓰지 않습니다.

첫 두 마디와 지정 화음 사건을 고정했지만, 모델이 그 옆에 생성한 추가 음은 제거하지 않았습니다. 이것이 반주/선율 충돌을 일으킬 수 있으며 실패 사유로 남겼습니다. 유효 후보가 없어 P2 기능/긴장 검사 이후 순위·상위 4개·규칙 후보와의 눈가림 청취는 실행하지 않았습니다. 실패 후보를 채택하거나 사용자 선택을 만들지 않았습니다.

## 로컬 결과와 재현

결과: `K:/MusicGeneration/amt-continuation/output/trial-v001/`의 `protocol.json`, `input.json`, `summary.json`, `verification.json`, `candidate-01`–`candidate-16`. 공개 Git에는 입력 악보·생성 음표·MIDI·가중치를 넣지 않습니다. 검수자는 먼저 summary와 verification을 확인하세요. 중단 기준에 도달했으므로 아래 명령은 이 기록의 재현 방법이지 추가 생성 지시가 아닙니다.

```powershell
$env:MUSICOMP_ROOT='K:\Music Composition'
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
& 'K:\Music Analysis\.venv\Scripts\python.exe' tools/amt_prepare_input.py --piece 'K:\MusicGeneration\motif-piece\output\piece-v002' --out output/trial-input.json
& 'K:\MusicGeneration\model-trial\output\amt-env\Scripts\python.exe' tools/amt_generate_trial.py --input output/trial-input.json --source 'K:\MusicGeneration\model-trial\output\anticipation-source' --cache 'K:\MusicGeneration\model-trial\output\hf-cache' --out output/trial-v001
& 'K:\Music Analysis\.venv\Scripts\python.exe' tools/amt_verify_trial.py output/trial-v001
```

별도 가상환경·공식 소스·캐시는 앞선 준비 꾸러미의 로컬 파일을 그대로 읽었고 네트워크 다운로드나 새 패키지 설치는 하지 않았습니다. 하드웨어는 Ryzen 5 7600, 6코어/12스레드, RAM 약 31.1 GiB. AMD 내장 GPU이며 CUDA 없음; GPU OOM으로 중단한 것이 아닙니다. 모델별 메모리가 아닌 같은 프로세스의 누적 최고 Working Set입니다.

코드 [공식 AMT 저장소](https://github.com/jthickstun/anticipation)와 [모델 카드](https://huggingface.co/stanford-crfm/music-small-800k)는 Apache 2.0. 학습 자료 Lakh MIDI에 관한 CC BY 4.0 설명과 개별 원곡의 권리는 구별합니다. 라이선스·환경의 최초 확인은 `2026-10-24_music-model-trial.md`에 있으며 이 시험은 새 데이터 학습이 아닙니다.

## 검증과 다음 판단

- 전체 테스트 **153 → 157개 통과**, 22.146초. after_rain MusicXML 바이트 회귀 포함.
- 원본 입력·16개 prefix·MIDI 헤더·결과 집계를 생성과 별도로 검증. `verification.json`에 출력 SHA-256와 실행 코드 지문 저장.
- P3는 기존 감사 결과 대중18/30·재즈20/30·고전13/30으로 중단 상태 유지. 후보 순위에 적용하지 않음.
- P2의 실제 프레이즈 선택은 아직 없음. 다음 모델 실험은 이번 실패를 반복 실행해 통과시키는 작업이 아니라, 기보 조건 표현·성부 제약을 지원하는 입력 방식과 평가 프로토콜을 먼저 재설계하는 별도 작업이어야 합니다.
- main과 기본 생성 경로, musicomp/Music Analysis/MusicSearch는 수정하지 않았습니다.
