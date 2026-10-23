# P3 검수 요청: 발전 통계 전의 분석기 감사 — 중단 기준 도달

- 브랜치 `codex/development-stats`, origin/main `b2b06cd`에서 시작. P1/P2 코드 의존 없음.
- 상태: 자료·라이선스 조사, 장르별 30개 경계의 1차 직접 검토와 중단 판정 완료. **발전 분포 산출·후보 순위 적용은 중단**. 학습 데이터 적용 완료로 간주하지 않음.
- main·musicomp·MusicSearch·Music Analysis 수정 없음. 원음·곡별 판정표는 로컬 output에만 보존.

## 자료와 라이선스 확인

| 자료 | 확인한 근거 | 이번 사용 |
|---|---|---|
| musicomp 리드시트 원본 | README와 leadsheet_miner.py는 `Music Analysis/MusicXML/*Melody*.xml`을 지칭. 기존 HUMAN_CHORD_SOURCE_LICENSES.json은 작품별 권리 미제공으로 기록 | 로컬 연구용 감사 10곡. 원음·곡별 판정 공개 없음 |
| Wikifonia/ChoCo | ChoCo LICENSE.md: 일반 CC BY 4.0 및 NC 예외. 기존 감사 문서는 raw MXL 권리를 별도로 미확인 처리 | 중복 계통·원본 권리 미확인 때문에 이번 30개 감사에는 미사용 |
| RealBook 200 | PSjazzEval LICENSE는 소프트웨어 MIT. README는 200 리드시트·음이름 검증 설명, 원곡 권리 허가 별도 없음 | 로컬 연구용 감사 11곡. 중복 평가 버전은 제목별 첫 파일 하나만 사용 |
| 고전 MusicXML | Mozart/Beethoven/Chopin 폴더. 원작과 특정 편집 악보의 권리는 구분. 기존 local_musicxml 감사는 작품별 자료 미제공 | 로컬 연구용 감사 10곡. 특정 편집본 공개 권리 확보로 간주하지 않음 |

근거 파일: `K:/Music Analysis/docs/harmony/HUMAN_CHORD_SOURCE_LICENSES.json`, `K:/MusicSearch/data/classical-corpora/choco/LICENSE.md`, `K:/MusicSearch/data/jazz-corpora/charlie-parker-50-solos/LICENSE` 및 README. [ChoCo 상위 라이선스](https://github.com/smashub/choco/blob/main/LICENSE.md). KYSing·AI Hub·DCML은 사용하지 않음.

## 변경한 파일과 동작

- `musigen/development_stats.py`: prepare, aggregate. 기본값 `analyze_motifs(mel)`과 `segment_layers(mel,key,motifs)`를 실행. 선율만 입력하고 화음 피드백·계수 조정 없음.
- 각 파일의 처음 48마디, 끝에 강제로 잘린 마지막 프레이즈 제외, 작품당 앞의 3개 이내, 장르별 30개. 파일명 해시 순서로 후보 작품 고정. 전체 장르를 대표하는 무작위 표본은 아님.
- 기존 `load_melody(...,use_given_chords=False)`는 첫 파트의 같은 onset 최상음을 취함. 고전의 성부 분리 정확도가 검증된 추출기라는 뜻이 아님. 다성 내성이 섞이는 경우 한계로 기록.
- `musigen/knowledge/development_stats.json`: 감사 집계·분모·라이선스·사용 중단 상태만 포함. 음정·리듬 분포, 원음, 곡별 마디는 없음. `default_enabled=false`, 모든 장르 `ranking_eligible=false`.
- `tests/test_development_stats.py`: 미검토·중복·근거 없는 판정·라이선스 미확인·유형 감사 미완료에서 적용 차단하는 테스트 6개.

## 직접 검토 결과와 중단

Codex가 악보에서 읽은 음표 사건(시작 위치·음가·음높이)의 앞뒤 맥락을 직접 검토했습니다. 청취 실험이나 인간 전문가의 정답 라벨이 아닙니다. 분명한 악구 시작·종결을 확인한 경우만 일치로, 내부 호흡이거나 불확실한 경우는 미확인으로 기록했습니다. 분석기가 제시한 경계만 검토했으므로 전체 경계 recall/F1이 아닙니다.

| 장르/자료 계열 | 표본 | 경계 확인 | 비율 | 판정 |
|---|---:|---:|---:|---|
| 대중 리드시트 계열 | 30 / 10곡 | 18 | 60.0% | 70% 미만, 통계 사용 중단 |
| 재즈 주제 계열 | 30 / 11곡 | 20 | 66.7% | 70% 미만, 통계 사용 중단 |
| 고전 피아노 | 30 / 10곡 | 13 | 43.3% | 70% 미만, 통계 사용 중단 |

장르는 폴더 계열 분류이며 대중 계열에 스탠더드·영화음악도 포함됩니다. 이 수치를 엄밀한 장르별 정확도로 일반화하지 않습니다.

주요 한계:

- 여린내기·긴 붙임줄·마디 중간 쉼을 상위 프레이즈 경계로 혼동함.
- 종지의 장음 도착을 앞두고 직전 짧은 음에서 구간을 자르거나, 내적 반복 단위를 전체 문장과 혼동함.
- 재즈 1개 표본은 음가 0과 비정상적인 onset 분모가 다수 나와 입력 읽기부터 미확인. 정상 경계로 세지 않음.
- 고전 피아노의 첫 파트 최상음 추출에는 내성·교대음이 섞여 있음.
- 기존 분석기는 sentence/period, inversion/fragment, continuation 기능을 직접 출력하지 않음. `new`/`varied`를 이 유형으로 재명명하지 않음.

경계 게이트에서 이미 중단했으므로 유형·변형 분류의 후속 정확도 판정 및 종지 직전 유형·이어짐 축소 분포를 완성한 것으로 기록하지 않습니다. 원음의 분포를 새 생성 규칙으로 승격하지 않았습니다. 규칙·계수 재튜닝도 하지 않았습니다.

## 재현·검증과 다음에 필요한 자료

```powershell
python -m musigen.development_stats prepare <로컬 manifest.json> --out <새 감사 폴더>
python -m musigen.development_stats aggregate <직접 판정을 채운 audit.json> --out <집계.json>
```

- 로컬 근거: `K:/Music Generation-codex/output/development-stats/manifest.json`, `audit-r1/audit.json`, `aggregate-log.json`.
- 판정표에 90개 표본 각각의 경계 판단·이유·검토자·미검증 항목 기록. 원본 파일 SHA-256 포함.
- 재즈 마지막 작품에서 31번째 표본이 만들어진 준비 코드의 상한 버그 수정. 사전에 정한 첫 30개만 유지했으며 결과에 따라 표본을 갈아끼우지 않음.
- 기준선 91 → **97개 전체 테스트 통과**. 기존 after_rain 바이트 회귀 통과. P2의 116개와 다른 독립 브랜치 테스트 수임.
- 다음 입력: 상위 프레이즈 경계와 성부가 확인된 장르별 선율, sentence/period 및 동기 변형에 대한 정답 라벨, 각 자료의 재사용 범위. 이번 표본의 수치를 올리기 위한 규칙 확장은 제안하지 않음.
