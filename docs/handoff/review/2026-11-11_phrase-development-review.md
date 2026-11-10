# 검수 요청 · 현재 곡의 프레이즈 발전 비교

브랜치 `codex/phrase-development-review`, 작업 트리 `K:\MusicGeneration\phrase-comparison`.

사용자 원문: “화성 진행과 변형이 좀 다채로워졌네요.”, “해 보죠. 앞에서 제안한 과정들도 쭉 진행하세요.” 화성에 대한 긍정적 의견을 곡 전체 승인이나 B 선택으로 확대하지 않았습니다. 모차르트 스타일 시험은 보류 상태입니다.

origin/main 72ca816에서 시작해 선행 여섯 커밋을 가져왔습니다. 이번 변경은 d6f7ca7 이후이며 이전 codex/phrase-reference-library f75b43d까지의 변경을 포함하므로 중복 병합에 주의해 주세요.

변경 파일: `musigen/phrase_review.py`(`evidence`, `assemble`, `run`), `tests/test_phrase_review.py`, 안내 문서·README. 기존 완성곡의 정확한 LH·표현을 공유하면서 단선율 발전을 비교합니다. 곡별 제목·마디 설명은 output 입력의 presentation에 있고 생성 규칙에 작품별 분기는 없습니다.

전: `K:\MusicGeneration\motif-piece\output\piece-v002`. 후: `output/review-v002`, <http://127.0.0.1:8797/index.html>. 24마디 A/B 각 멜로디+화성/피아노 솔로 XML·PDF·HTML. B 독주 WAV도 저장했습니다.

17–24마디를 비교하세요. 17–18은 재현 그대로, 19는 원모티프 앞부분의 2박 조각 두 번, 20은 절정 앞 쉼, 21은 원 리듬을 드러내는 단순화, 22는 종지 접근 앞 쉼, 23은 E5를 2박으로 늘인 뒤 D5–B4–C5 진행입니다. 화성·왼손·빠르기·셈여림·페달과 첫 8마디는 동일하며, 실제 수정은 19–23마디 RH뿐입니다. 음가 확대·조각 선택은 작곡 판단이지 관찰에서 자동 검출한 기법이 아닙니다.

검증: 전체 unittest 144개 통과. 출처 ID·변경 마디·관찰/판단 분리 검사 3개 추가. 두 XML 형식 독립 재읽기, 고정 조건, 인쇄용 XML 음표 일치. B PDF 두 페이지 이미지 최종 검수(각 파일 1쪽). Verovio 증6 레이블은 인쇄용만 It⁺⁶ 글자로 표시, native XML 보존.

브라우저: 비교 화면·B 피아노 샘플 WAV/PDF 다운로드·Roman Numeral Analysis·17–20 구간 재생 확인. 받은 PDF 바이트 일치. WAV PCM 무음/클리핑 검사 통과, 상세 값은 delivery_qa.json. 원 TAVERN 라이선스 사본을 함께 보관했습니다.

오류 A/B 0개, 경고 A 1개(기존 21마디 F#5 이웃음 분류), B 0개. 쉼 13.5→16박. 자동 프레이즈 A는 끝 17–24, B는 17–20과 22–24로 관찰하며 21마디가 독립 프레이즈로 보고되지 않습니다. 계획 경계 전체 일치나 품질 향상을 주장하지 않습니다. 청취 평가는 남아 있고 기본 적용은 안 했습니다. P3 분석 계수, musicomp, 원자료, main은 바꾸지 않았습니다.

로컬 서버 재시작: `python -m http.server 8797 --bind 127.0.0.1 --directory output/review-v002`. 다음 꾸러미는 A/B 선택 없이 다른 모티프에서 동일한 자료 참조·발전 작성 과정을 시험합니다.
