"""Create an in-memory notation view for the motif range picker."""
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

LIMIT=16*1024*1024


def compressed_score(raw):
    try:
        with ZipFile(BytesIO(raw)) as archive:
            def read_member(name,maximum):
                item=archive.getinfo(name)
                if item.file_size>maximum:raise ValueError('압축을 푼 악보가 읽기 한도를 넘습니다.')
                return archive.read(item)
            meta=ET.fromstring(read_member('META-INF/container.xml',128*1024))
            roots=meta.findall('.//{*}rootfile')
            item=next((r for r in roots if r.get('media-type')=='application/vnd.recordare.musicxml+xml'),None)
            if item is None:item=next(iter(roots),None)
            if item is None:raise ValueError('MXL에 악보 목록이 없습니다.')
            xml=ET.fromstring(read_member(item.attrib['full-path'],LIMIT))
            if xml.tag.split('}')[-1]!='score-partwise':raise ValueError('파트별 MusicXML 악보가 필요합니다.')
            return {'xml':ET.tostring(xml,encoding='unicode')}
    except (BadZipFile,KeyError,ET.ParseError,RuntimeError,OSError) as exc:
        raise ValueError('MXL 악보를 읽을 수 없습니다.') from exc


def midi_score(raw):
    from music21 import midi
    from music21.musicxml.m21ToXml import GeneralObjectExporter
    if (len(raw)<14 or raw[:4]!=b'MThd' or int.from_bytes(raw[8:10],'big') not in (0,1)
            or not 0<int.from_bytes(raw[12:14],'big')<32768):
        raise ValueError('박 기준 시간이 있는 표준 MIDI 형식 0 또는 1 파일을 열어 주세요.')
    try:
        mf=midi.MidiFile()
        mf.readstr(raw)
        tracks=[t for t in mf.tracks if t.hasNotes()]
        if not tracks:raise ValueError('MIDI 파일에 음표가 없습니다.')
        if any(sum(e.time for e in t.events if e.isDeltaTime())>mf.ticksPerQuarterNote*16384 for t in mf.tracks):
            raise ValueError('MIDI가 한 번에 기보할 수 있는 길이를 초과합니다.')
        score=midi.translate.midiFileToStream(mf,quantizePost=True,quarterLengthDivisors=(4,3))
        for i,part in enumerate(score.parts):
            track=tracks[i] if len(score.parts)==len(tracks) else None
            label=f'트랙 {track.index+1}' if track is not None else f'파트 {i+1}'
            original=next((e.data for e in track.events if e.type==midi.MetaEvents.SEQUENCE_TRACK_NAME),b'') if track else b''
            name=original.decode('utf8','replace').strip() if isinstance(original,bytes) else str(original).strip()
            name=name or part.partName
            part.partName=label+(' · '+name if name else '')
            part.id=f'P{i+1}'
        xml=GeneralObjectExporter(score).parse()
    except ValueError:raise
    except Exception as exc:
        raise ValueError('MIDI를 악보로 변환하지 못했습니다. 파일과 기보 가능한 음표를 확인하세요.') from exc
    if len(xml)>LIMIT:raise ValueError('변환한 MIDI 악보가 16MB를 초과합니다.')
    root=ET.fromstring(xml)
    parts=root.findall('part')
    for index,definition in enumerate(root.findall('./part-list/score-part')):
        old=definition.get('id')
        identity=f'T{tracks[index].index+1}' if len(parts)==len(tracks) else f'P{index+1}'
        definition.set('id',identity)
        next(p for p in parts if p.get('id')==old).set('id',identity)
    return {'xml':ET.tostring(root,encoding='unicode')}
