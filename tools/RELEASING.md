# Releasing Fieldbook

1. Update VERSION and CHANGELOG.md. Run the checks in TESTING.md.
2. Regenerate the manifest with `python tools/make-manifest.py .`, then run
   `node tools/validate.mjs .`. Never include private notes, credentials, .venv,
   node_modules, caches or local Obsidian state in the source kit.
3. Verify starter-seeds.json contains only pristine default settings. They are
   separate from live user-owned config files so deploying from a used vault does
   not leak its Inbox/provider settings. Keep optional skill permissions in sync.
4. Create fresh starters with deploy-vault.py and verify plugin asset/source hashes.
   Include third-party notices and the matching Templater source archive.
5. Package the source and starter folders. The Python updater accepts a release
   ZIP or extracted folder. Run its preview against a disposable previous version.

Plugin upgrades require fresh pinned versions/checksums, source/license review,
settings-schema verification and live app acceptance. Do not replace binaries under
an existing version hash. The deployment helper downloads but never executes them.

## Portable packaging and native acceptance

Run `python tools/package-release.py OUTPUT --starters` for clean source and
plugin-free starter ZIPs offline. Add `--plugin-cache PATH` to bundle the pinned,
hash-verified plugin cache. Regenerate the manifest first after release edits.
`python tools/release-acceptance.py` packages actual artifacts, upgrades legacy
TaskNotes layouts with Unicode/spaces and a read-only note, verifies manager
activation and backup/restore preservation. CI runs this on Windows, Linux and
macOS. Run these checks on each target operating system.

For 1.0 also run `python tools/usage-acceptance.py`: it tests real CLI onboarding, resume, review snapshots/cancellation, field conflicts and unchanged permissions in all packaged profiles with no network.

When changing a complete record template, keep its stable templateName and advance
templateVersion for structural/semantic changes. Pure spelling fixes need no bump.
Keep starter-seeds.json's Review-format copy in sync. Task body is a versioned
fragment, not a complete record. Test provenance through rendered CLI records.
