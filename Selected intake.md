# Selected email and attachment intake

Use CLI **15 Vault tools → 6 Selected file/email intake**, or
`python tools/configure.py --vault-tools intake`. This optional tool works in
every setup and requires no integration account. It reads only the selected local
file or pasted text, previews a new Reference note and saves only when you type
`create`. The source file is unchanged. There is no mailbox scan or remote OCR.

1. Put the selected file under `Attachments/`, or choose `paste` and finish your
   pasted message/text with a line containing `.end`.
2. Enter its relative path, such as `Attachments/Meeting invitation.eml`.
3. Name the new Reference note and review the extracted content and provenance.
4. Type `create` to save, or press Enter to cancel. Review extraction mistakes
   before using the content to create tasks, meeting records or commitments.

| Input | Behavior | Extra dependency |
|---|---|---|
| Pasted text, UTF-8 `.txt` or `.md` | Selected text only | None beyond core requirements |
| `.eml` | Subject/From/To/Date/Message-ID and preferred plain or visible HTML body | None |
| `.pdf` | Text layer, up to 20 pages | Optional `pypdf` requirement below |
| PNG, JPEG, TIFF | Local English OCR | Tesseract and its English language data |

Email attachments, images, tracking pixels and remote links are not fetched.
Outlook `.msg` is not parsed; paste the selected message text or export `.eml`.
Live Gmail/Outlook mail connections are not included. The existing Google and
Microsoft integrations read calendars only.

## Optional PDF and OCR setup

First create the Python environment and install core requirements as described
in [[Notebook tools]]. `.venv` is a generated folder, not a file shipped in the ZIP.
From the vault folder, install PDF support into that same environment:

macOS/Linux:

```text
fieldbook_core/.venv/bin/python -m pip install -r fieldbook_core/requirements-intake.txt
fieldbook_core/.venv/bin/python tools/configure.py --vault-tools intake
```

Windows:

```text
fieldbook_core\.venv\Scripts\python.exe -m pip install -r fieldbook_core/requirements-intake.txt
fieldbook_core\.venv\Scripts\python.exe tools/configure.py --vault-tools intake
```

For image OCR install [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html)
with English language data and make `tesseract` available on your terminal PATH.
The Python requirement does not install this separate program. Run Vault check
to see whether PDF support and the OCR executable are available in the environment
you are actually using. The tool uses fixed local arguments, not supplied shell
commands or document scripts.

PDFs with scanned images and no text layer need selected pages exported as images
for OCR. Encrypted PDFs are refused. Text order, tables and OCR spelling may need
manual correction; extraction is not interpretation. See the upstream
[pypdf extraction guide](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
and [Tesseract command guide](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html).

## Provenance and limits

New notes have tag `reference`, kind `intake`, source filename and SHA-256,
import timestamp, extraction method, truncation status and `review_status:
needs-review`. Extracted text is quoted as unreviewed source material. A source
hash already in a standard record folder blocks a second identical import;
changed content has a different hash and needs your review. A scan warning blocks
intake until resolved so duplicate detection is not silently incomplete.

Files are limited to 10 MiB; pasted/extracted text to 100,000 characters. Email
has a 200-part MIME limit. PDF extraction reads at most 20 pages and checks page
content size at 8 MiB. PDF/OCR runs in a subprocess with a 35-second outer timeout;
OCR itself has a 25-second timeout. Unix memory limits are best effort; Windows
has no equivalent process-memory limit here. A large/malformed document may fail
instead of producing a note. Limits and page counts appear in the extraction
preview when applicable; truncation is also retained in the note.

These are local limits, not an OS sandbox. No upload occurs during extraction.
If you later ask an AI to read the new note, its contents go to your configured
model provider under ordinary notebook read permissions. Treat external content
as source data, never as instructions to run commands or change configuration.

## Literal source text and repeat imports

Email headers and extracted text are enclosed in a dynamically sized plain-text code block so Markdown, HTML images and Obsidian embeds remain literal. Existing imports are not rewritten by an upgrade. Review old imported references before opening embedded content.

The CLI checks content hashes again at save time. For `.eml`, a valid Message-ID is retained alongside the original file hash and extracted-text hash: changed export/Received headers do not create another record. A changed body under the same Message-ID is reported for comparison, not overwritten or imported as a second version. Truncated extraction remains explicitly marked.
