# Releasing fieldbook

1. Edit `VERSION` (0.x.y while lightly tested: bump the minor for a new
   feature or a field change, the patch for a fix).
2. Add a `## x.y.z - date` entry at the top of `CHANGELOG.md`.
3. If note fields are renamed or moved, add `.opencode/migrations/NNNN-*.json`
   (see 0001 for the ops: `toLabeledList`, `renameKey`, `addKey`). Adding a
   field needs no migration; add an `addKey` op only so `-Backfill` can add it
   to old notes.
4. `ruby tools/make-manifest.rb .`, then commit everything together.
5. Tag `vX.Y.Z` and create the GitHub release with the changelog entry as
   its notes: `gh release create vX.Y.Z --title "fieldbook X.Y.Z" --notes-file <entry>`.
   The source zip GitHub attaches is what `update-fieldbook.ps1 -From` takes.
