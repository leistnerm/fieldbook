---
description: Suggest links for unlinked people mentions and identify missing contacts
---
Input: $ARGUMENTS (days, all, or default 14 days).
Get the date with notebook_today. Use notebook_query kind person for existing names
and aliases. Query modified_from for the chosen period; for all, start with the
30 most recently changed notes and report that limit. Search known names literally
and read matching notes to distinguish existing wikilinks, quotes and plain mentions.
Flag possible new contacts only where source context supports that they are people.
Show candidates with source links and uncertainty. Offer link/create/skip. Never
create a contact or modify a mention without acceptance, unless explicitly included
in the original request. Basic contacts need no company/work fields. Use
notebook_write with fresh hashes. Do not run arbitrary shell scripts.
