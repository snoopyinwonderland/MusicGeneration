"""Read catalog metadata and the notation view exposed by the local MusicSearch service."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen


def fetch(route):
    try:
        with urlopen('http://127.0.0.1:5178/api/'+route,timeout=25) as response:
            raw=response.read(24*1024*1024+1)
    except HTTPError as exc:
        raise ValueError('음악 검색에서 해당 악보를 열 수 없습니다.') from exc
    except (URLError,TimeoutError,OSError) as exc:
        raise RuntimeError('음악 검색 서버(5178)에 연결할 수 없습니다. XML 파일 열기도 이용할 수 있습니다.') from exc
    if len(raw)>24*1024*1024:raise ValueError('이 악보는 작업실에서 열 수 있는 크기를 초과합니다.')
    try:return json.loads(raw)
    except ValueError as exc:raise RuntimeError('음악 검색 서버의 응답을 확인하세요.') from exc


def catalog(data):
    query=data.get('query')
    if not isinstance(query,str) or not 2<=len(query.strip())<=120:raise ValueError('검색어를 2–120자로 입력하세요.')
    return fetch('catalog/search?'+urlencode({'q':query.strip(),'limit':25}))


def score(data):
    work=data.get('workId')
    if not isinstance(work,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',work):raise ValueError('악보 ID를 확인하세요.')
    item=fetch('work/'+work+'?notationOnly=1&start=1')
    if not item.get('xml'):raise ValueError('이 작품에는 열 수 있는 XML이 없습니다.')
    return {key:item.get(key) for key in ('xml','title','workId','streamId','sourceId','restrictedPreviewActive')}
