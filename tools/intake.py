#!/usr/bin/env python3
"""Selected local file/email intake, preview only until a separate create action."""
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile

LIMIT=10*1024*1024
MAX_TEXT=100000

class VisibleText(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','head'):self.hidden+=1
        if tag in ('p','br','div','li','tr','h1','h2','h3'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','head') and self.hidden:self.hidden-=1
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)

def clean_html(value):
    parser=VisibleText();parser.feed(value);return ''.join(parser.parts)

def extract(path):
    data=path.read_bytes()
    if len(data)>LIMIT:raise ValueError('Selected file exceeds 10 MiB')
    suffix=path.suffix.lower();metadata={}
    if suffix=='.eml':
        message=BytesParser(policy=policy.default).parsebytes(data)
        if sum(1 for _ in message.walk())>200:raise ValueError('Email exceeds 200 MIME parts')
        part=message.get_body(preferencelist=('plain','html'))
        if part is None:raise ValueError('Email has no readable body')
        body=part.get_content()
        if part.get_content_type()=='text/html':body=clean_html(body)
        metadata={k:str(message.get(k,''))[:1000] for k in ('Subject','From','To','Date','Message-ID')}
        method='Selected email body; attachments and remote content not imported'
    elif suffix in ('.txt','.md'):
        body=data.decode('utf-8-sig');method='UTF-8 text'
    elif suffix in ('.pdf','.png','.jpg','.jpeg','.tif','.tiff'):
        with tempfile.TemporaryDirectory(prefix='fieldbook-intake-') as temp:
            selected=Path(temp)/('selected'+suffix);selected.write_bytes(data)
            try:
                process=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).with_name('intake-worker.py')),str(selected),'pdf' if suffix=='.pdf' else 'image'],capture_output=True,text=True,timeout=35)
            except subprocess.TimeoutExpired:raise ValueError('Extraction exceeded 35 seconds; choose a smaller document') from None
            if len(process.stdout)>650000:raise ValueError('Extraction output exceeds its limit')
            try:result=json.loads(process.stdout)
            except ValueError:raise ValueError('Extraction failed; check optional dependencies and resource limits') from None
            if process.returncode or 'error' in result:raise ValueError(result.get('error','Extraction failed'))
            return result
    else:raise ValueError('Choose a PDF, PNG/JPEG/TIFF image, UTF-8 text, Markdown or .eml file. Outlook .msg is not supported; paste its text instead.')
    return {'text':body[:MAX_TEXT],'truncated':len(body)>MAX_TEXT,'method':method,'email':metadata}
