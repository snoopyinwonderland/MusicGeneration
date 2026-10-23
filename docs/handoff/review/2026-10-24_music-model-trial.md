# P4 검수 요청: AMT 소형 모델 환경 준비 (생성 시험 미완료)

- 브랜치: `codex/music-model-trial`, origin/main `b2b06cd`에서 시작.
- 상태: **설치·모델 로딩·전방 계산만 검증**. 16개 생성, 필터, 눈가림 청취 비교는 아직 실행하지 않음.
- P2 프레이즈의 실제 사용자 선택을 기다림. m6(3/4), m5(4/4)는 모티프 선택이며 프레이즈 선택으로 대신 기록하지 않음.
- 기존 `piece` 기본 경로, musigen/musicomp 환경, main 수정 없음. 모델 실행은 별도 스크립트를 명시적으로 호출할 때만 가능.

## 변경 파일

- `tools/amt_preflight.py`: 모델 ID와 revision을 고정한 CPU 로딩 및 전방 계산 검사. `trust_remote_code=False`, 출력 차원·유한값 검사, 패키지 버전·소요 시간 기록. `--offline`은 캐시만 사용.
- `tools/amt-requirements.txt`: 별도 환경의 최소 의존성. torch는 공식 CPU 저장소에서 별도 설치.
- 이 검수 요청서. 생성 연결기·P2 필터 연결기는 아직 없음.

## 모델·자료 출처

| 대상 | 확인 근거 | 해석 |
|---|---|---|
| AMT 코드 | [공식 저장소](https://github.com/jthickstun/anticipation), `LICENSE.txt` Apache 2.0 | 소스 revision `af37397922665a0fb8d474d7988b0f3755a38d45`를 로컬 output에만 보관 |
| 작은 가중치 | [music-small-800k](https://huggingface.co/stanford-crfm/music-small-800k), 모델 카드 Apache 2.0 | revision `fa800530aa1126dd6b58b38f3bdb8fcec9c9d4f5`, 파라미터 128,103,936 |
| 학습 자료 | [Stanford 공개 설명](https://crfm.stanford.edu/2023/06/16/anticipatory-music-transformer.html): Lakh MIDI, CC BY 4.0 설명 | 데이터셋 표기와 개별 원곡 권리는 구분. 원곡 재배포 허가로 간주하지 않음. 자료 자체를 새로 수집하거나 학습하지 않음 |

가중치·소스 복제본·가상환경·캐시·실험 악보는 `output/` 아래에만 있으며 Git에 넣지 않음. 다른 모델은 시험하지 않음.

## 하드웨어와 환경

- AMD Ryzen 5 7600, 6코어/12스레드. 물리 RAM 33,444,220,928 bytes.
- AMD Radeon(TM) Graphics, 드라이버 32.0.11024.2. Windows CIM AdapterRAM 보고값 536,870,912 bytes. 공유 메모리를 포함한 총 가용 GPU 메모리 측정값은 아님.
- NVIDIA/CUDA 없음. 이번 준비는 CPU 6스레드로 실행. **GPU 메모리 부족 오류가 관찰된 것은 아님**.
- Python 3.12.13, torch 2.14.1+cpu, transformers 4.46.3. 최소 의존성은 requirements 파일에 고정.
- 상위 프로젝트의 오래된 전체 requirements(transformers 4.29.2 등)를 그대로 설치한 환경은 아님. 최신 Python 환경에서 검증한 것은 가중치 로딩과 전방 계산까지이며, 상위 생성기의 호환성은 후속 시험 대상.
- 별도 환경: `K:/MusicGeneration/model-trial/output/amt-env`. 기존 Python 환경에는 패키지를 설치하지 않음.

## 재현

작업트리 루트에서 실행:

```powershell
& 'K:\Music Analysis\.venv\Scripts\python.exe' -m venv output\amt-env
& .\output\amt-env\Scripts\python.exe -m pip install torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
& .\output\amt-env\Scripts\python.exe -m pip install -r tools\amt-requirements.txt
& .\output\amt-env\Scripts\python.exe tools\amt_preflight.py
& .\output\amt-env\Scripts\python.exe tools\amt_preflight.py --offline
```

최초 로딩 13.06초(다운로드 포함), 출력 `[1,4,55028]`, CPU 확인. 이것은 6마디 생성 시간이나 청취 품질의 증거가 아님. 고정 revision의 오프라인 재검증 결과는 로컬 `output/preflight-offline.json`에 남김.

## 남은 검증과 멈춤 기준

1. P2에서 실제 고른 프레이즈의 선택 기록과 후보 SHA를 확인.
2. 해당 후보의 1–2마디 기본 악상·8마디 화음을 고정하고, 나머지 6마디 선율을 16회 생성. 시간·최대 메모리·원본 출력을 기록.
3. 박자·조성 및 P2 기능·긴장 검사를 적용. 탈락 원인과 분모를 기록하고, 입력 고정 여부도 검사. 부족한 후보를 임의 보정해 합격시키지 않음.
4. 유효 후보가 4개 미만이면 여기서 중단. 4개 이상이면 상위 4개와 규칙 후보 4개를 눈가림 비교하고 실제 사용자 선택 뒤 출처 공개.

현재 생성 횟수 **0**, 탈락 비율·생성 시간·최대 메모리·청취 선택 **미측정**. 설치에 하루 이상 걸림 / GPU OOM / 16개 중 유효 4개 미만 중 현재 도달한 조건은 없음. 프레이즈 선택 대기는 모델 실패로 세지 않음.

들어 볼 모델 후보는 아직 없음. P2 입력을 고르는 페이지:
- [3/4 · m6의 프레이즈 p1–p4](http://127.0.0.1:8792/lyrical_34/stage2_phrases/index.html)
- [4/4 · m5의 프레이즈 p1–p4](http://127.0.0.1:8792/bright_44/stage2_phrases/index.html)

기본 작곡 경로를 수정하지 않았으므로 이번 준비에 음악적 개선 주장을 붙이지 않음. 전체 회귀 검사 결과는 아래 검증 기록에 남김.

## 검증 기록

- 기준선 91 → 91개 전체 테스트 통과(14.34초). `test_notation_expression`의 after_rain MusicXML 바이트 회귀 포함.
- 첫 실행은 샌드박스 임시 폴더 쓰기 권한 때문에 20개 오류. 코드 수정 없이 TEMP/TMP를 이 작업트리의 `output/test-temp`로 지정한 뒤 전체 통과. 초기 실패를 모델 또는 음악 코드 오류로 세지 않음.
- 고정 revision의 캐시 전용 로딩 0.51초, 출력 `[1,4,55028]`, 모든 logit 유한값 확인. 생성 횟수는 계속 0.
- 추가 단위 테스트 없음. 새 코드는 별도 실행하는 로딩 검사이며 실제 실행 결과와 기존 경로 회귀로 검증.
