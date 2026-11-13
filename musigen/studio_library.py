"""Render the local listening catalog into the studio landing page."""
import json
from html import escape
from urllib.parse import unquote, urlsplit


def library_html(root):
    manifest = root / 'library.json'
    if not manifest.is_file():
        return ''

    def link(label, url, css=''):
        target = urlsplit(url)
        path = unquote(target.path)
        if target.scheme or target.netloc or path.startswith('/') or '\\' in path:
            return ''
        file = (root / path).resolve()
        if not file.is_relative_to(root.resolve()) or not file.is_file():
            return ''
        classes = f' class="{css}"' if css else ''
        return f'<a{classes} href="{escape(url)}">{escape(label)}</a>'

    groups = []
    for group in json.loads(manifest.read_text(encoding='utf-8')):
        works = []
        for work in group['works']:
            title = link(work['title'], work['url'], 'work-title')
            if not title:
                continue
            versions = ''.join(link(row['label'], row['url']) for row in work.get('versions', []))
            extra = f'<div class="work-versions">{versions}</div>' if versions else ''
            works.append(f'<li><h3>{title}</h3><p>{escape(work["detail"])}</p>{extra}</li>')
        if works:
            groups.append(f'<section class="library-group"><h2>{escape(group["title"])}</h2>'
                          f'<ul>{"".join(works)}</ul></section>')

    if not groups:
        return ''

    return ('<section id="library" aria-labelledby="library-title">'
            '<div class="library-head"><h1 id="library-title">작품 라이브러리</h1>'
            '<a href="#newMotif">모티프 입력</a></div>'
            '<label for="library-search" hidden>작품 검색</label>'
            '<input id="library-search" type="search" placeholder="곡 제목이나 편성 검색" hidden>'
            '<p id="library-empty" role="status" hidden>검색 결과가 없습니다.</p>'
            + ''.join(groups) + '</section>')
