# Starter plugin sources and notices

The Fieldbook source kit does not contain plugin binaries. deploy-vault.py obtains
the exact releases listed in starter-plugins.json and checks SHA-256 hashes. Ready
starter ZIPs include those unmodified binaries in .obsidian/plugins/.

- TaskNotes 4.13.8, Callum Alpass: [release](https://github.com/callumalpass/tasknotes/releases/tag/4.13.8),
  [source](https://github.com/callumalpass/tasknotes/tree/4.13.8). License notice:
  tools/licenses/tasknotes-LICENSE.txt (MIT).
- Templater 2.25.1, SilentVoid and contributors:
  [release](https://github.com/SilentVoid13/Templater/releases/tag/2.25.1),
  [source](https://github.com/SilentVoid13/Templater/tree/2.25.1). License:
  tools/licenses/templater-LICENSE.txt (GNU AGPL v3). The matching source archive
  accompanies the binary at .obsidian/plugins/templater-obsidian/source.tar.gz in
  ready starter vaults. The source includes its package metadata/build configuration.

Plugins retain their own licenses. Fieldbook configuration and documentation are
separate. Downloaded JavaScript runs only when Obsidian loads the enabled plugin;
the deployment helper does not execute it. Review third-party code and updates
according to your own needs. The supplied starter requires Obsidian 1.13.0 or newer
because of the pinned Templater manifest (TaskNotes itself requires 1.12.2).

Settings checked against TaskNotes 4.13.8 settings/defaults.ts,
types/settings.ts and bootstrap/defaultBasesFiles.ts, and Templater 2.25.1
settings/Settings.ts and settings/LocalSettings.ts. Default view generation uses
commandFileMapping, so its paths all point to Views/. Local Templater startup,
file-creation and shell-command switches default off; they are not enabled here.
