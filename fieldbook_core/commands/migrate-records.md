---
description: Preview a small batch of existing records against current templates, with verified backups and information-preserving edits
---
Input: $ARGUMENTS
Read AGENTS.md and load record-migration. Default to five explicitly selected records,
preview only. Compare templateName/templateVersion without guessing legacy provenance.
Preserve all content, links, custom fields and integration identities. Require a
verified backup and approval of the exact batch before writes. Stop after each batch.
