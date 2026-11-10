# 같은 곡에서 프레이즈 발전 비교

`phrase_review`는 기존 완성곡의 실제 왼손·표현을 고정하고, 새로 작성한 단선율 발전안을 비교하는 선택 명령입니다. 자료에서 완성 선율을 복사하거나 후보를 자동 선발하지 않습니다.

작업 폴더: `motif.json`(기준선과 동일), `development.json`(수정안), `references.json`(프레이즈 참조 관찰), `decisions.json`(feedback, uses, presentation). uses에는 바뀐 bars, 실제 관찰된 reference_ids, observation, decision을 각각 적습니다. 변경 마디와 기록이 다르거나 미평가 출처를 참조하면 중단합니다. presentation에는 a/b의 label·description, focus_title·focus를 적습니다.

```powershell
$env:MUSICOMP_ROOT='K:\Music Composition'
python -m musigen.phrase_review --baseline 'K:\MusicGeneration\motif-piece\output\piece-v002' --work output/review-input --out output/review-v002 --protected-bars 8
```

기준선은 `blueprint_solo` 결과 폴더입니다. 그 안의 발전 설계, 모티프, `solo_score.json`과 실제 MusicXML을 다시 읽어 확인합니다. 전체 화성, 국소 조성, 빠르기, 셈여림, 표현, 왼손과 첫 N마디를 고정합니다. 기존 코드의 반주 스냅샷을 없애서 선택 전 반주로 돌아가는 일을 피하고, 실제 실현된 음표를 직접 공유합니다.

A/B 각각 멜로디+상세 화성, 피아노 솔로의 XML·HTML·검사·상세 화성 정보를 만듭니다. `a/`, `b/`에 같은 이름의 PDF를 별도로 렌더링한 뒤 `--pages-only`로 감상 페이지에 연결합니다. 입력·기준선 XML·고정 반주 해시가 바뀌면 새 출력 폴더가 필요합니다.

2026-11-11 결과: <http://127.0.0.1:8797/index.html>. 첫 8마디와 전체 화성을 보존했고 실제 변경은 19–23마디 오른손뿐입니다. B의 조각내기, 쉼, 긴 음은 자료의 관련성·끝 음가 관찰을 해석한 작성자의 결정입니다. 두 악보의 오류는 없으며, 주선율 쉼은 A 13.5박/B 16박입니다. 자동 프레이즈 관찰과 청취 판단은 다릅니다. 특히 B의 21마디는 별도 프레이즈로 보고되지 않아, 설계의 여섯 구간을 모두 자동 검증했다고 볼 수 없습니다.
