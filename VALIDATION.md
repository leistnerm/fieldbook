# Checking Fieldbook

Use a disposable vault when checking a new installation. Never use real credentials
or private records in fixtures or public reports.

## Automated checks

See [Testing](tools/TESTING.md) for requirements and commands. The checks cover
record handling, read-only provider adapters, permissions, setup activation,
backups, upgrade preservation, restore, onboarding and review/conflict previews.
HTTP fixtures do not establish live account access or provider availability.

## Check your installation

1. Run `python fieldbook.py --check`, then Maintenance > Vault checks.
2. Open a disposable starter in Obsidian and check Dashboard and its active views.
3. Insert a template into a named empty note in Editing view, or use
   **Templater: Create new note from template**. Check both properties and body.
4. In AI assistant, check command discovery, read/search access and approval or denial
   of local writes. A denied write must leave the note unchanged.
5. Use Integrations to test each connection you choose to configure. Check sign-in,
   read access and scope separately; a saved configuration is not a successful test.
6. Back up the disposable vault, change a note, then restore. Verify the newer
   note remains recoverable in the pre-restore backup.

Plugin rendering, filesystem behavior, OAuth and host permission prompts depend
on the installed applications and environment; check them on each intended device.
