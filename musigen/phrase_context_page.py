"""Local, self-contained phrase-context reference browser (no score generation)."""
import json
from pathlib import Path


def write_page(library, target):
    from musigen.phrase_context import export_reference
    data={**library,'exports':{u['id']:export_reference(library,u['id']) for u in library['windows']}}
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    template=Path(__file__).with_name('phrase_context.html').read_text(encoding='utf-8')
    Path(target).write_text(template.replace('/*CONTEXT_DATA*/',payload),encoding='utf-8')
