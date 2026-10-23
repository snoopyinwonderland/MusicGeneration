/* Portable clips from explicit MusicXML timing. No uploads or automatic clipboard reads. */
const MotifTools = (() => {
  class F {
    constructor(n, d = 1) {
      if (!Number.isSafeInteger(n) || !Number.isSafeInteger(d) || d <= 0) throw Error('잘못된 음가입니다.');
      const gcd = (a, b) => b ? gcd(b, a % b) : a;
      const g = gcd(Math.abs(n), d);
      this.n = n / g;
      this.d = d / g;
    }
    add(b) { return new F(this.n * b.d + b.n * this.d, this.d * b.d); }
    sub(b) { return new F(this.n * b.d - b.n * this.d, this.d * b.d); }
    cmp(b) { return this.n * b.d - b.n * this.d; }
    toString() { return this.d === 1 ? String(this.n) : `${this.n}/${this.d}`; }
    static read(s) {
      if (!/^\d+(\/\d+)?$/.test(String(s))) throw Error('음가는 양의 정수 또는 분수여야 합니다.');
      const [n, d = '1'] = String(s).split('/');
      return new F(Number(n), Number(d));
    }
  }
  const child = (node, tag) => [...node.children].find(n => n.localName === tag);
  const children = (node, tag) => [...node.children].filter(n => n.localName === tag);
  const value = (node, tag, fallback = '') => child(node, tag)?.textContent.trim() ?? fallback;
  const max = (a, b) => a.cmp(b) >= 0 ? a : b;
  const pitchPattern = /^([A-G])(#{1,2}|b{1,2})?(-?\d)$/;

  function validate(clip) {
    if (clip?.format !== 'musicanote-motif' || clip.version !== 1) throw Error('MUSICANOTE 모티프 version 1이 필요합니다.');
    if (!Array.isArray(clip.events) || !clip.events.length || clip.events.length > 4096) throw Error('음 또는 쉼 1–4096개를 넣어 주세요.');
    let total = new F(0);
    let sounding = false;
    for (const e of clip.events) {
      const d = F.read(e.duration);
      if (d.cmp(new F(1, 12)) < 0 || d.cmp(new F(256)) > 0 || 24 % d.d) throw Error('현재는 일반 음가와 셋잇단음표(최소 1/12박)를 지원합니다.');
      if (!Array.isArray(e.pitches) || e.pitches.length > 10) throw Error('pitches는 음이름 목록이어야 합니다.');
      for (const name of e.pitches) {
        const p = typeof name === 'string' && name.match(pitchPattern);
        if (!p) throw Error(`지원하지 않는 음이름: ${name}`);
        const acc = p[2] || '';
        const midi = 12 * (Number(p[3]) + 1) + {C:0,D:2,E:4,F:5,G:7,A:9,B:11}[p[1]] + (acc.includes('#') ? acc.length : -acc.length);
        if (midi < 0 || midi > 127) throw Error('MIDI 0–127 범위 밖의 음입니다.');
      }
      if (new Set(e.pitches).size !== e.pitches.length) throw Error('한 화음에 중복된 음이 있습니다.');
      sounding ||= e.pitches.length > 0;
      total = total.add(d);
    }
    if (!sounding) throw Error('소리 나는 음이 하나 이상 필요합니다.');
    return total.toString();
  }

  function parseMusicXML(text, filename = '붙여넣은 악보') {
    const doc = new DOMParser().parseFromString(text, 'application/xml');
    if (doc.querySelector('parsererror') || doc.documentElement.localName !== 'score-partwise') {
      throw Error('score-partwise MusicXML(.xml/.musicxml)을 열어 주세요.');
    }
    const names = new Map([...doc.querySelectorAll('score-part')].map(p => [p.getAttribute('id'), value(p, 'part-name')]));
    const streams = new Map();
    let uid = 0;
    for (const part of children(doc.documentElement, 'part')) {
      const partId = part.getAttribute('id');
      let divisions = 1, nominal = new F(4), base = new F(0);
      for (const [index, measure] of children(part, 'measure').entries()) {
        let cursor = new F(0), extent = new F(0), previous = null;
        const number = measure.getAttribute('number') || String(index + 1);
        for (const node of measure.children) {
          if (node.localName === 'attributes') {
            if (child(node, 'divisions')) divisions = Number(value(node, 'divisions'));
            if (!Number.isSafeInteger(divisions) || divisions <= 0) throw Error('잘못된 divisions입니다.');
            const time = child(node, 'time');
            if (time) {
              const beats = value(time, 'beats');
              const type = Number(value(time, 'beat-type'));
              if (!/^\d+$/.test(beats) || !type) throw Error('복합 표기 박자표는 아직 지원하지 않습니다.');
              nominal = new F(4 * Number(beats), type);
            }
          } else if (node.localName === 'backup' || node.localName === 'forward') {
            const d = new F(Number(value(node, 'duration')), divisions);
            cursor = node.localName === 'backup' ? cursor.sub(d) : cursor.add(d);
            if (cursor.n < 0) throw Error('마디 시작보다 앞선 음 위치입니다.');
            extent = max(extent, cursor);
            previous = null;
          } else if (node.localName === 'note') {
            const staff = value(node, 'staff', '1'), voice = value(node, 'voice', '1');
            const key = JSON.stringify([partId, staff, voice]);
            if (!streams.has(key)) streams.set(key, {key, part:partId, name:names.get(partId) || partId, staff, voice, events:[], warnings:[]});
            const stream = streams.get(key);
            if (child(node, 'grace')) { stream.warnings.push('장식음은 가져오지 않았습니다.'); continue; }
            const dur = new F(Number(value(node, 'duration')), divisions);
            if (dur.n <= 0) throw Error('0 이하 음가를 가져올 수 없습니다.');
            const chord = !!child(node, 'chord');
            if (chord && (!previous || previous.stream !== stream)) throw Error('화음의 성부 연결을 확인해 주세요.');
            const on = chord ? previous.on : cursor;
            const pitches = [];
            if (!child(node, 'rest')) {
              const p = child(node, 'pitch');
              if (!p) throw Error('무음정 타악기·타브 악보는 아직 지원하지 않습니다.');
              const step = value(p, 'step'), alter = Number(value(p, 'alter', '0')), octave = value(p, 'octave');
              if (!Number.isInteger(alter) || Math.abs(alter) > 2) throw Error('미분음은 아직 지원하지 않습니다.');
              pitches.push(step + (alter > 0 ? '#'.repeat(alter) : 'b'.repeat(-alter)) + octave);
            }
            const id = `motif-note-${++uid}`;
            node.setAttribute('id', id);
            const ties = children(node, 'tie').map(t => t.getAttribute('type'));
            if (chord) {
              if (previous.event.dur.cmp(dur)) throw Error('길이가 다른 화음음은 성부를 나누어 가져와 주세요.');
              previous.event.pitches.push(...pitches);
              previous.event.ids.push(id);
              previous.event.tieStarts.push(ties.includes('start'));
              previous.event.tieStops.push(ties.includes('stop'));
            } else {
              const event = {on:base.add(on), dur, measure:number, measureIndex:index, offset:on, pitches, ids:[id],
                             tieStarts:[ties.includes('start')], tieStops:[ties.includes('stop')]};
              stream.events.push(event);
              previous = {stream, on, event};
              cursor = cursor.add(dur);
            }
            extent = max(extent, on.add(dur));
          }
        }
        base = base.add(measure.getAttribute('implicit') === 'yes' ? extent : max(extent, nominal));
      }
    }
    const voices = [...streams.values()].filter(s => s.events.length);
    for (const s of voices) s.events.sort((a,b) => a.on.cmp(b.on));
    if (!voices.length) throw Error('가져올 음을 찾지 못했습니다.');
    return {filename, voices, xml:new XMLSerializer().serializeToString(doc)};
  }

  function clipRange(score, stream, first, last, name = 'a') {
    if (!Number.isInteger(first) || !Number.isInteger(last) || first < 0 || last >= stream.events.length || last < first) throw Error('시작과 끝 음의 순서를 확인해 주세요.');
    const selected = stream.events.slice(first, last + 1);
    const events = [], warnings = [...new Set(stream.warnings)];
    let cursor = selected[0].on, previous = null;
    for (const e of selected) {
      if (e.on.cmp(cursor) < 0) throw Error('선택한 성부에서 음이 겹칩니다. 다른 성부를 선택해 주세요.');
      if (e.on.cmp(cursor) > 0) {
        events.push({duration:e.on.sub(cursor).toString(), pitches:[]});
        previous = null;
      }
      if (e.tieStarts.some(Boolean) && !e.tieStarts.every(Boolean) || e.tieStops.some(Boolean) && !e.tieStops.every(Boolean)) throw Error('일부 화음음만 붙임줄인 경우는 아직 지원하지 않습니다.');
      const tied = previous && previous.tieStarts.every(Boolean) && e.tieStops.every(Boolean)
        && JSON.stringify([...previous.pitches].sort()) === JSON.stringify([...e.pitches].sort());
      if (tied) events.at(-1).duration = F.read(events.at(-1).duration).add(e.dur).toString();
      else events.push({duration:e.dur.toString(), pitches:[...e.pitches]});
      cursor = e.on.add(e.dur);
      previous = e;
    }
    if (selected[0].tieStops.some(Boolean) || selected.at(-1).tieStarts.some(Boolean)) warnings.push('구간 밖 붙임줄을 잘라 선택한 길이만 가져왔습니다.');
    const clip = {format:'musicanote-motif', version:1, name,
      events, source:{file:score.filename, part:stream.part, staff:stream.staff, voice:stream.voice,
        start:{measure:selected[0].measure, offset:selected[0].offset.toString()},
        end:{measure:selected.at(-1).measure, offset:selected.at(-1).offset.add(selected.at(-1).dur).toString()},
        pitch:'written', repeats:'not-expanded'}, warnings};
    validate(clip);
    return clip;
  }
  return {parseMusicXML, clipRange, validate, F};
})();

(() => {
  const el = id => document.getElementById(id);
  let score = null, voice = null, renderer = null, clip = null;
  let previewNodes = [], previewTimer = 0;
  const status = message => { el('motifStatus').textContent = message; };
  const run = fn => async () => { try { await fn(); } catch (e) { status(e.message); } };
  const option = (value, label) => {
    const node = document.createElement('option');
    node.value = value;
    node.textContent = label;
    return node;
  };
  function selected() {
    const start = Number(el('motifStart').value), end = Number(el('motifEnd').value);
    for (const node of el('motifScore').querySelectorAll('.motif-selected')) {
      node.classList.remove('motif-selected');
      node.style.fill = '';
      node.style.stroke = '';
    }
    if (!voice) return;
    for (const event of voice.events.slice(start, end + 1)) {
      for (const id of event.ids) {
        const node = el('motifScore').querySelector(`[id="${id}"]`);
        if (node) { node.classList.add('motif-selected'); node.style.fill = '#b35925'; node.style.stroke = '#b35925'; }
      }
    }
    status(end < start ? '끝 음은 시작 음 뒤에서 선택해 주세요.' : `${end - start + 1}개 음·쉼 선택. ‘선택 구간을 모티프로’를 누르면 보관함에 담습니다.`);
  }
  function chooseVoice() {
    voice = score.voices[Number(el('motifVoice').value)];
    for (const id of ['motifStart','motifEnd']) {
      el(id).replaceChildren(...voice.events.map((e,i) => option(i, `${e.measure}마디 +${e.offset}박 · ${e.pitches.join('+') || '쉼'} (${e.dur}박)`)));
      el(id).disabled = false;
    }
    const firstMeasure = voice.events[0].measureIndex;
    el('motifEnd').value = String(voice.events.findLastIndex(e => e.measureIndex === firstMeasure));
    el('motifExtract').disabled = false;
    selected();
  }
  async function openXML(text, filename) {
    const parsed = MotifTools.parseMusicXML(text, filename);
    if (!tk) throw Error('악보 엔진을 준비 중입니다. 잠시 뒤 다시 열어 주세요.');
    renderer ||= new verovio.toolkit();
    renderer.setOptions({pageWidth:2000,pageHeight:60000,scale:40,svgViewBox:true,breaks:'auto',adjustPageHeight:true,header:'none',footer:'none'});
    if (!renderer.loadData(parsed.xml)) throw Error('악보를 표시하지 못했습니다.');
    score = parsed;
    el('motifScore').innerHTML = Array.from({length:renderer.getPageCount()}, (_,i) => renderer.renderToSVG(i+1)).join('');
    for (const svg of el('motifScore').querySelectorAll('svg')) { svg.style.width='100%'; svg.style.height='auto'; svg.style.minWidth='640px'; }
    el('motifVoice').replaceChildren(...score.voices.map((s,i) => option(i, `${s.name} · 보표 ${s.staff} · 성부 ${s.voice}`)));
    el('motifVoice').disabled = false;
    chooseVoice();
  }
  function acceptClip(value) {
    const quarters = MotifTools.validate(value);
    clip = value;
    clip.name = el('motifName').value.trim() || clip.name || 'a';
    el('motifText').value = JSON.stringify(clip, null, 2);
    el('motifListen').disabled = false;
    el('motifCopy').disabled = false;
    el('motifSave').disabled = false;
    status(`모티프 ${clip.name}: ${clip.events.length}개 사건, 4분음표 ${quarters}개 길이. ${(clip.warnings || []).join(' ')}`);
  }
  async function loadText(text, filename) {
    if (text.trimStart().startsWith('<')) await openXML(text, filename);
    else {
      const value = JSON.parse(text);
      el('motifName').value = value.name || 'a';
      acceptClip(value);
    }
  }
  function currentClip() {
    const value = JSON.parse(el('motifText').value);
    acceptClip(value);
    return clip;
  }
  el('openMotifStudio').addEventListener('click', () => {
    el('motifStudio').open = true;
    el('motifStudio').scrollIntoView({behavior:'smooth',block:'start'});
  });
  el('motifCurrent').addEventListener('click', run(() => openXML(cur.xml, `${cur.piece}-${cur.info.version}.musicxml`)));
  el('motifFile').addEventListener('change', run(async () => {
    const file = el('motifFile').files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) throw Error('10MB 이하 파일을 열어 주세요.');
    await loadText(await file.text(), file.name);
  }));
  el('motifVoice').addEventListener('change', chooseVoice);
  el('motifStart').addEventListener('change', selected);
  el('motifEnd').addEventListener('change', selected);
  el('motifScore').addEventListener('click', event => {
    const target = event.target.closest('g.note, g.rest, g.mRest');
    if (!target || !voice) return;
    const index = voice.events.findIndex(e => e.ids.includes(target.id));
    if (index < 0) { status('선택한 파트·보표·성부의 음을 눌러 주세요.'); return; }
    const mode = document.querySelector('input[name="motifPick"]:checked').value;
    el(mode === 'start' ? 'motifStart' : 'motifEnd').value = String(index);
    if (mode === 'start') {
      if (Number(el('motifEnd').value) < index) el('motifEnd').value = String(index);
      document.querySelector('input[name="motifPick"][value="end"]').checked = true;
    }
    selected();
  });
  el('motifExtract').addEventListener('click', run(() => acceptClip(MotifTools.clipRange(score, voice, Number(el('motifStart').value), Number(el('motifEnd').value), el('motifName').value.trim() || 'a'))));
  el('motifLoadText').addEventListener('click', run(() => loadText(el('motifText').value, '붙여넣은 악보')));
  el('motifPaste').addEventListener('click', run(async () => {
    try { await loadText(await navigator.clipboard.readText(), '클립보드 악보'); }
    catch (e) { status('클립보드를 읽지 못했습니다. 아래 보관함에 Ctrl+V로 붙여넣고 ‘붙여넣은 내용 읽기’를 눌러 주세요. ' + e.message); }
  }));
  el('motifCopy').addEventListener('click', run(async () => {
    const value = currentClip();
    try { await navigator.clipboard.writeText(JSON.stringify(value, null, 2)); status('모티프를 복사했습니다. 다른 보관함이나 대화에 붙여넣을 수 있습니다.'); }
    catch { el('motifText').focus(); el('motifText').select(); status('자동 복사가 허용되지 않았습니다. 선택된 내용을 Ctrl+C로 복사해 주세요.'); }
  }));
  function silence() {
    clearTimeout(previewTimer);
    for (const node of previewNodes) { try { node.stop(); } catch {} }
    previewNodes = [];
    el('motifSilence').disabled = true;
  }
  el('motifSilence').addEventListener('click', silence);
  el('play').addEventListener('click', silence);
  el('stop').addEventListener('click', silence);
  el('pick').addEventListener('change', silence);
  window.addEventListener('pagehide', silence);
  el('motifListen').addEventListener('click', run(async () => {
    const value = currentClip();
    if ($('timbre').value === 'piano' && !pianoReady) throw Error('피아노 음원을 준비 중입니다.');
    silence();
    cancelComparison();
    stop();
    ctx ||= new (window.AudioContext || window.webkitAudioContext)();
    await ctx.resume();
    let position = 0;
    const start = ctx.currentTime + .08;
    for (const event of value.events) {
      const fraction = MotifTools.F.read(event.duration);
      const seconds = fraction.n / fraction.d * 60 / 72;
      for (const name of event.pitches) {
        const [,step,acc = '',octave] = name.match(/^([A-G])(#{1,2}|b{1,2})?(-?\d)$/);
        const pitch = 12 * (Number(octave) + 1) + {C:0,D:2,E:4,F:5,G:7,A:9,B:11}[step] + (acc.includes('#') ? acc.length : -acc.length);
        previewNodes.push(...tone(start + position, seconds * .95, pitch, .07 / Math.sqrt(event.pitches.length)));
      }
      position += seconds;
    }
    el('motifSilence').disabled = false;
    previewTimer = setTimeout(silence, (position + .7) * 1000);
    status('모티프를 듣는 중입니다. 기보한 쉼과 음가로, 페달 없이 재생합니다.');
  }));
  el('motifSave').addEventListener('click', run(() => {
    const value = currentClip();
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type:'application/json'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = (value.name || 'motif').replace(/[^\w가-힣-]/g, '_') + '.motif.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status('모티프 JSON을 저장했습니다. 다음 작업에서 파일로 다시 열 수 있습니다.');
  }));
})();
