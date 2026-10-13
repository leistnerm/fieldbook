# Useful Obsidian additions

Start with the configured TaskNotes + Templater core. Add a tool to solve a real
friction point; more plugins also mean more settings to maintain. These suggestions
have links to their primary documentation.

| Feature | Benefit for Fieldbook | Recommendation |
|---|---|---|
| Bookmarks (core) | Pin Dashboard, Inbox, Cheat Sheet, active course or a saved search | Enabled in starter; bookmark your own favorites |
| Canvas (core) | Map a project, course topic, research question or decision with linked notes | Enabled in starter; use note cards for evidence you want searchable |
| Backlinks / outgoing links / Properties (core) | Find relationships and inspect structured fields | Enabled in starter; complements AI linking suggestions |
| File recovery (core) | Recover recent accidental changes | Enabled; still keep an independent backup |
| Web Clipper (browser extension) | Capture sources into Reference/Research with a URL | Optional first addition for reading/research |
| QuickAdd (community) | Capture menus for Inbox, meetings or accomplishments, including when AI is off | Optional; start with simple capture/template choices |
| Omnisearch (community) | Ranked search inside Obsidian with fuzzy matching | Optional; complements the AI's local search tools |

QuickAdd should capture to Inbox or the existing schema; do not introduce a second
task system. Test any TaskNotes task-creation macro on a sample before regular use.
Only install scripts/macros you intend to run. AI assistant's notebook permissions do
not control Obsidian plugins or a QuickAdd macro.

Canvas text-only cards are not normal note records and do not appear in backlinks;
convert reusable content to note cards. The scoped AI tools currently read Markdown,
not Canvas binaries/JSON diagrams or attachment contents. PDF/image search in
Omnisearch needs its documented extraction support; this kit does not install it.

For college/research, Zotero is worth a separate citation workflow. The former
mgmeyers/obsidian-zotero-integration repository currently redirects to a community
archive, so this starter does not bundle it. Keep citation metadata and annotations
in an explicit export/import workflow until choosing a maintained integration.

Bases already supplies structured dashboards; add Dataview only for a query that
Bases and the notebook tools cannot express. Another Tasks plugin would overlap
TaskNotes. Daily notes are optional for a diary/day log, but tasks should remain
linked task notes rather than copied daily checkboxes. Automatic Markdown/YAML
formatters should be tested before they touch TaskNotes-managed properties.

Sources: [Bookmarks](https://obsidian.md/help/plugins/bookmarks),
[Canvas](https://obsidian.md/help/plugins/canvas),
[Web Clipper](https://obsidian.md/help/web-clipper),
[QuickAdd](https://github.com/chhoumann/quickadd),
[Omnisearch](https://github.com/scambier/obsidian-omnisearch),
[Zotero integration archive](https://github.com/community-archive/obsidian-zotero-integration).
