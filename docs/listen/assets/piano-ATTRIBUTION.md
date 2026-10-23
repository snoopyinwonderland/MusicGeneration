# 피아노 샘플 출처

Fluid (R3) General MIDI SoundFont — Frank Wen and contributors, © 2000–2002, 2008 Frank Wen.
MP3 렌더링·패키징: Benjamin Gleitzman 및 gleitz/midi-js-soundfonts.

- 원본: https://github.com/gleitz/midi-js-soundfonts/tree/044fab8e1456bfafc5776e86dfd6bb8697149aef
- 라이선스: Creative Commons Attribution 3.0 United States, https://creativecommons.org/licenses/by/3.0/us/
- 전문: https://creativecommons.org/licenses/by/3.0/us/legalcode.en
- 당시 README를 UPSTREAM_README.md에 보관했습니다. 이 은행은 upstream의 CC BY 표기를 따릅니다.

변경: MUSICANOTE에서 MIDI21–108 중 3반음마다 한 음(30개)을 골라 JS 할당을 JSON으로 바꾸고 MIME을 audio/mpeg로 정규화했습니다. MP3 바이트는 그대로입니다. MusicGeneration은 검증된 피아노 은행만 복사했으며 다른 악기는 포함하지 않습니다. 은행·원본·개별 음의 SHA256은 manifest.json에 있습니다. 브라우저는 가까운 샘플을 최대 1반음 이동합니다. 고정 벨로시티이며 음량·주법·페달을 Web Audio로 반영하는 미리듣기입니다.

샘플을 재배포할 때 저작자·출처·라이선스·변경 표시를 유지하세요. 저작자 보증을 의미하지 않습니다. 이 라이선스는 프로젝트 코드나 자작 악보의 라이선스를 바꾸지 않습니다.

재생 시 각 디코딩 샘플의 최대 진폭을 0.8로 맞춥니다. 6배의 미리듣기 gain은 잠정 믹스 값이며 원본 MP3 파일은 바꾸지 않습니다. WAV는 합산 진폭이 0.98을 넘을 때만 전체 감쇠하여 클리핑을 막습니다.
