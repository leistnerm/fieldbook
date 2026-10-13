#!/usr/bin/env python3
"""Bounded local extraction subprocess; never fetches links or executes document content."""
import json
from pathlib import Path
import sys

MAX_TEXT=100000

def main():
    # A timeout is also enforced by the parent. Unix memory limits are best effort;
    # Windows uses the same size/page/time limits but has no resource module.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(1024*1024*1024,1024*1024*1024))
    except (ImportError,ValueError,OSError):pass
    path=Path(sys.argv[1]);kind=sys.argv[2]
    if kind=='pdf':
        try:from pypdf import PdfReader
        except ImportError:raise ValueError('Install fieldbook_core/requirements-intake.txt for PDF text extraction') from None
        reader=PdfReader(path)
        if reader.is_encrypted:raise ValueError('Encrypted PDFs are not supported; use a permitted unlocked copy')
        total=len(reader.pages);parts=[];length=0
        for i in range(min(total,20)):
            page=reader.pages[i];stream=page.get_contents()
            if stream is not None and len(stream.get_data())>8*1024*1024:raise ValueError('PDF page content exceeds 8 MiB')
            part='[Page '+str(i+1)+']\n'+(page.extract_text() or '')
            parts.append(part[:MAX_TEXT-length]);length+=len(parts[-1])
            if length>=MAX_TEXT:break
        content='\n\n'.join(parts)[:MAX_TEXT]
        if not any((p.split('\n',1)[1] if '\n' in p else '').strip() for p in parts):raise ValueError('No text layer found; export selected pages as images and use local OCR')
        return {'text':content,'truncated':total>len(parts) or length>=MAX_TEXT,'pages_read':len(parts),'pages_total':total,'method':'PDF text layer; reading order/tables may need correction'}
    if kind=='image':
        import shutil, subprocess
        exe=shutil.which('tesseract')
        if not exe:raise ValueError('Install Tesseract locally for image OCR; no cloud OCR is used')
        # Fixed arguments and a private output file; no shell or caller-supplied flags.
        out=path.parent/'ocr'
        result=subprocess.run([exe,str(path),str(out),'-l','eng'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=25)
        target=out.with_suffix('.txt')
        if result.returncode or not target.exists():raise ValueError('Local OCR failed; check the image and installed English language data')
        with target.open('rb') as f:data=f.read(MAX_TEXT*4+1)
        content=data.decode('utf-8',errors='replace')
        if not content.strip():raise ValueError('OCR found no text')
        return {'text':content[:MAX_TEXT],'truncated':len(content)>MAX_TEXT,'method':'Local Tesseract English OCR; review recognition errors'}
    raise ValueError('Unsupported extraction kind')

if __name__=='__main__':
    try:print(json.dumps(main(),ensure_ascii=True))
    except Exception as error:
        message=str(error) if isinstance(error,ValueError) else 'Extraction failed or exceeded resource limits'
        print(json.dumps({'error':message[:250]}));sys.exit(1)
