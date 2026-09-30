<#
Brings this vault up to a newer fieldbook release. Shows what it would do;
changes nothing unless you add -Apply.

  update-fieldbook.ps1 -From <release folder or .zip> [-Apply] [-Backfill] [-SkipGitCheck]

Get the release from https://github.com/leistnerm/fieldbook/releases (download
the zip; you don't need to unpack it). Then, in PowerShell, from this vault:

  .\.opencode\scripts\update-fieldbook.ps1 -From "$HOME\Downloads\fieldbook-0.2.0.zip"

What it does, per file listed in the release's fieldbook-manifest.json:
  - not in your vault yet: added.
  - in your vault and unchanged since the last release: replaced.
  - you edited it: yours is kept; the new one is saved next to it as
    <name>.fieldbook-new for you to compare and merge, then delete.
  - identical, or unchanged in the release: left alone.
Your notes, opencode.json, jira.json, Types.md, Templates\Review-format.md and
AGENTS.local.md are never touched (they are not in the manifest).
Migrations (.opencode\migrations\*.json) then rename or move fields in your
existing notes (top-level single-line frontmatter fields only). Adding empty
new fields to old notes is optional: -Backfill.
With -Apply, uncommitted changes must be committed first (so git can undo the
update); -SkipGitCheck skips that check.
#>
param(
  [Parameter(Mandatory = $true)][string]$From,
  [switch]$Apply,
  [switch]$Backfill,
  [switch]$SkipGitCheck
)
$ErrorActionPreference = "Stop"
$vault = Split-Path (Split-Path $PSScriptRoot)
$utf8 = New-Object System.Text.UTF8Encoding($false)

function Read-Text([string]$p) { [IO.File]::ReadAllText($p, $utf8) }
function Get-Hash([string]$p) {
  $t = (Read-Text $p) -replace "`r`n", "`n"
  $sha = [Security.Cryptography.SHA256]::Create()
  ([BitConverter]::ToString($sha.ComputeHash($utf8.GetBytes($t))) -replace '-', '').ToLower()
}

$tmp = $null
try {
  if (Test-Path -LiteralPath $From -PathType Leaf) {
    if ($From -notlike "*.zip") { throw "-From must be a release folder or a .zip file." }
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ("fieldbook-" + [guid]::NewGuid())
    Expand-Archive -LiteralPath $From -DestinationPath $tmp
    $searchRoot = $tmp
  } elseif (Test-Path -LiteralPath $From -PathType Container) {
    $searchRoot = $From
  } else { throw "Not found: $From" }

  $mf = Get-ChildItem -LiteralPath $searchRoot -Recurse -Force -Filter "fieldbook-manifest.json" | Select-Object -First 1
  if (-not $mf) { throw "No fieldbook-manifest.json in $From - is this a fieldbook release?" }
  $kit = $mf.DirectoryName
  if ((Resolve-Path -LiteralPath $kit).Path -eq (Resolve-Path -LiteralPath $vault).Path) { throw "-From is this vault itself." }

  $new = (Read-Text $mf.FullName) | ConvertFrom-Json
  $oldPath = Join-Path $vault "fieldbook-manifest.json"
  $old = $null
  if (Test-Path -LiteralPath $oldPath) { $old = (Read-Text $oldPath) | ConvertFrom-Json }
  $appliedPath = Join-Path $vault "fieldbook-applied.json"
  $applied = @()
  if (Test-Path -LiteralPath $appliedPath) { $applied = @(((Read-Text $appliedPath) | ConvertFrom-Json).migrations) }

  $oldVer = if ($old) { "$($old.version)" } else { "unknown (no manifest: first update of this vault)" }
  "Installed: $oldVer    Release: $($new.version)"
  if (-not $old) { "No earlier manifest here, so every file that differs is treated as edited and saved as .fieldbook-new." }

  # ---- files
  $add = @(); $replace = @(); $conflict = @(); $same = 0; $removed = @()
  foreach ($p in $new.files.PSObject.Properties) {
    $rel = $p.Name; $newHash = "$($p.Value)"
    $srcFile = Join-Path $kit $rel
    if (-not (Test-Path -LiteralPath $srcFile)) { throw "The manifest lists a file the release lacks: $rel" }
    $dest = Join-Path $vault $rel
    if (-not (Test-Path -LiteralPath $dest)) {
      if ($old -and $old.files.PSObject.Properties[$rel]) { $removed += $rel } else { $add += $rel }
      continue
    }
    $destHash = Get-Hash $dest
    if ($destHash -eq $newHash) { $same++; continue }
    $oldHash = $null
    if ($old) { $o = $old.files.PSObject.Properties[$rel]; if ($o) { $oldHash = "$($o.Value)" } }
    if ($oldHash -and $oldHash -eq $newHash) { $same++; continue }
    if ($oldHash -and $destHash -eq $oldHash) { $replace += $rel } else { $conflict += $rel }
  }
  $gone = @()
  if ($old) {
    foreach ($p in $old.files.PSObject.Properties) {
      if (-not $new.files.PSObject.Properties[$p.Name] -and (Test-Path -LiteralPath (Join-Path $vault $p.Name))) { $gone += $p.Name }
    }
  }

  # ---- migrations
  $migDir = Join-Path $kit ".opencode\migrations"
  $migs = @()
  if (Test-Path -LiteralPath $migDir) {
    $migs = @(Get-ChildItem -LiteralPath $migDir -Filter "*.json" | Sort-Object Name | ForEach-Object { (Read-Text $_.FullName) | ConvertFrom-Json })
  }
  $pending = @($migs | Where-Object { $applied -notcontains $_.id })

  $skipRe = '\\(\.obsidian|\.opencode|\.git|\.trash|node_modules|Templates)\\|\\Transcripts\\\.work\\'
  $notes = @(Get-ChildItem -LiteralPath $vault -Recurse -Force -File -Filter "*.md" | Where-Object { $_.FullName.Substring($vault.Length) -notmatch $skipRe })

  function Find-Key($fm, [string]$key) {
    for ($i = 0; $i -lt $fm.Count; $i++) { if ($fm[$i] -match ('^' + [regex]::Escape($key) + ':')) { return $i } }
    return -1
  }
  function Get-Rest([string]$line) { ($line -replace '^[^:]*:\s*', '').Trim() }

  # Returns @{ text; changes; skipped; manual } for one note, or $null if it isn't a target.
  function Edit-Note([string]$text, $mig) {
    $m = [regex]::Match($text, '^(---\r?\n)([\s\S]*?)(\r?\n---)')
    if (-not $m.Success) { return $null }
    $fmText = $m.Groups[2].Value
    $tag = [regex]::Escape("$($mig.tag)")
    if ($fmText -notmatch ('(?m)^tags:.*\b' + $tag + '\b') -and $fmText -notmatch ('(?m)^\s*-\s*' + $tag + '\s*$')) { return $null }
    $nl = if ($text.Contains("`r`n")) { "`r`n" } else { "`n" }
    $fm = New-Object 'System.Collections.Generic.List[string]'
    foreach ($l in ($fmText -split '\r?\n')) { $fm.Add($l) }
    $changes = @(); $skipped = 0; $manual = @()
    foreach ($op in $mig.ops) {
      switch ($op.op) {
        "addKey" {
          if ((Find-Key $fm $op.key) -ge 0) { break }
          if ($Backfill) { $fm.Add("$($op.key): $($op.value)"); $changes += "add $($op.key)" } else { $skipped++ }
        }
        "renameKey" {
          $i = Find-Key $fm $op.from
          if ($i -ge 0 -and (Find-Key $fm $op.to) -lt 0) { $fm[$i] = "$($op.to): $(Get-Rest $fm[$i])"; $changes += "rename $($op.from) -> $($op.to)" }
        }
        "toLabeledList" {
          $i = Find-Key $fm $op.from
          if ($i -lt 0) { break }
          $val = (Get-Rest $fm[$i]).Trim('"', "'")
          $t = Find-Key $fm $op.to
          if ($val -eq "") { $fm.RemoveAt($i); $changes += "drop empty $($op.from)"; break }
          $entry = '"' + $op.label + ': ' + $val.Replace('\', '\\').Replace('"', '\"') + '"'
          if ($t -lt 0) {
            $fm.RemoveAt($i); $fm.Add("$($op.to): [$entry]")
          } else {
            $rest = Get-Rest $fm[$t]
            if ($rest -eq "" -and $t + 1 -lt $fm.Count -and $fm[$t + 1] -match ^\s*-) { $manual += "$($op.from) has a value but $($op.to) is written as a block list; move it by hand"; break }
            if ($rest -eq "" -or $rest -eq "[]") { $fm[$t] = "$($op.to): [$entry]" }
            elseif ($rest -match '^\[(.*)\]$') { $fm[$t] = "$($op.to): [$($Matches[1]), $entry]" }
            else { $manual += "$($op.from) has a value but $($op.to) is written as a block list; move it by hand"; break }
            $fm.RemoveAt($i)
          }
          $changes += "move $($op.from) -> $($op.to)"
        }
      }
    }
    $out = $text
    if ($changes.Count) { $out = $m.Groups[1].Value + ($fm -join $nl) + $m.Groups[3].Value + $text.Substring($m.Length) }
    @{ text = $out; changes = $changes; skipped = $skipped; manual = $manual }
  }

  $current = @{}   # path -> note text after the migrations so far; each note is written once
  $report = @()
  foreach ($mig in $pending) {
    $touched = 0; $skippedNotes = 0; $manualLines = @()
    foreach ($n in $notes) {
      $src = if ($current.ContainsKey($n.FullName)) { $current[$n.FullName] } else { Read-Text $n.FullName }
      $r = Edit-Note $src $mig
      if (-not $r) { continue }
      if ($r.changes.Count) { $touched++; $current[$n.FullName] = $r.text }
      if ($r.skipped) { $skippedNotes++ }
      foreach ($mm in $r.manual) { $manualLines += "$($n.Name): $mm" }
    }
    $report += "Migration $($mig.id) - $($mig.title): $touched note(s) to change" + $(if ($skippedNotes) { ", $skippedNotes could also get empty new fields (use -Backfill)" } else { "" })
    foreach ($ml in $manualLines) { $report += "  MANUAL: $ml" }
    if ($mig.note) { $report += "  Note: $($mig.note)" }
  }

  # ---- report
  ""
  "Add ($($add.Count)):";               $add | ForEach-Object { "  + $_" }
  "Replace, unchanged by you ($($replace.Count)):"; $replace | ForEach-Object { "  ~ $_" }
  "Edited by you, new copy saved as .fieldbook-new ($($conflict.Count)):"; $conflict | ForEach-Object { "  ! $_" }
  "Already current: $same file(s)"
  if ($removed.Count) { "Deleted by you, not re-added ($($removed.Count)):"; $removed | ForEach-Object { "  x $_" } }
  if ($gone.Count) { "No longer in fieldbook (left in place; delete if you don't use them):"; $gone | ForEach-Object { "  - $_" } }
  if ($report.Count) { ""; $report }

  $log = Join-Path $kit "CHANGELOG.md"
  if (Test-Path -LiteralPath $log) {
    $shown = @()
    foreach ($sec in ((Read-Text $log) -split '(?m)^(?=## )')) {
      if ($sec -notmatch '^## (\d+\.\d+\.\d+)') { continue }
      $v = [version]$Matches[1]
      $isNewer = $true
      if ($old -and "$($old.version)" -match '^\d+\.\d+\.\d+$') { $isNewer = $v -gt [version]"$($old.version)" }
      if ($isNewer -and $v -le [version]"$($new.version)") { $shown += $sec.TrimEnd() }
    }
    if ($shown.Count) { ""; "What's new:"; $shown }
  }

  if (-not $Apply) { ""; "Nothing changed. Run again with -Apply to do it."; return }

  # ---- apply
  if (-not $SkipGitCheck -and (Get-Command git -ErrorAction SilentlyContinue)) {
    $prev = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    $dirty = & git -C $vault status --porcelain 2>$null
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -eq 0 -and $dirty) { throw "Uncommitted changes in the vault. Commit them first (Obsidian Git: commit all), or rerun with -SkipGitCheck." }
  }
  $selfRel = ".opencode/scripts/update-fieldbook.ps1"
  foreach ($rel in (@($add) + @($replace) | Sort-Object { $_ -eq $selfRel })) {
    $dest = Join-Path $vault $rel
    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
    Copy-Item -LiteralPath (Join-Path $kit $rel) -Destination $dest -Force
  }
  foreach ($rel in $conflict) { Copy-Item -LiteralPath (Join-Path $kit $rel) -Destination ((Join-Path $vault $rel) + ".fieldbook-new") -Force }
  foreach ($k in $current.Keys) { [IO.File]::WriteAllText($k, $current[$k], $utf8) }
  Copy-Item -LiteralPath $mf.FullName -Destination $oldPath -Force
  $ids = @($applied) + @($pending | ForEach-Object { $_.id })
  $json = '{"version":"' + $new.version + '","migrations":[' + (($ids | ForEach-Object { '"' + $_ + '"' }) -join ",") + ']}'
  [IO.File]::WriteAllText($appliedPath, $json, $utf8)
  ""
  "Done. Version $($new.version). Merge each .fieldbook-new into your file (or delete it), then commit."
}
finally {
  if ($tmp -and (Test-Path -LiteralPath $tmp)) { Remove-Item -LiteralPath $tmp -Recurse -Force }
}
