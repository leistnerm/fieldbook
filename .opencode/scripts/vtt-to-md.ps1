<#
Converts a Teams transcript (.vtt) in the vault's Transcripts\ folder into a
readable markdown note (speaker turns, no cue ids) in Transcripts\.work\, a
folder git ignores. -Keep moves that note up into Transcripts\ (tracked by
git); -Remove deletes one named file from Transcripts\ or Transcripts\.work\
(nothing else).

  vtt-to-md.ps1 -Path "<file>.vtt" -Date 2026-09-29 -Title "Platform sync"
  vtt-to-md.ps1 -Keep "<converted note name>"
  vtt-to-md.ps1 -Remove "<file name>"

Prints the new note's path. No network, no model.
#>
param(
  [string]$Path,
  [string]$Date,
  [string]$Title,
  [string]$Remove,
  [string]$Keep
)
$ErrorActionPreference = "Stop"
$vault = Split-Path (Split-Path $PSScriptRoot)
$dir = Join-Path $vault "Transcripts"
$work = Join-Path $dir ".work"
$utf8 = New-Object Text.UTF8Encoding $false

function Get-PlainName([string]$n) {
  $p = [IO.Path]::GetFileName($n)
  if ($p -ne $n -or $n -match '[*?]') { throw "Give a plain file name, no path or wildcard." }
  $p
}

if ($Keep) {
  $name = Get-PlainName $Keep
  $from = Join-Path $work $name
  $to = Join-Path $dir $name
  if (-not (Test-Path -LiteralPath $from)) { throw "Not found in Transcripts\.work: $name" }
  if (Test-Path -LiteralPath $to) { throw "Already exists in Transcripts: $name" }
  Move-Item -LiteralPath $from -Destination $to
  "Kept $name"
  exit
}

if ($Remove) {
  $name = Get-PlainName $Remove
  $found = $false
  foreach ($d in @($dir, $work)) {
    $target = Join-Path $d $name
    if (Test-Path -LiteralPath $target -PathType Leaf) { Remove-Item -LiteralPath $target; "Removed $name"; $found = $true }
  }
  if (-not $found) { "Not found: $name" }
  exit
}

if (-not $Path -or -not $Date -or -not $Title) { throw "Need -Path, -Date and -Title." }
if ($Date -notmatch '^\d{4}-\d{2}-\d{2}$') { throw "-Date must be YYYY-MM-DD." }
$src = if ([IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path $dir $Path }
$src = [IO.Path]::GetFullPath($src)
if (-not $src.StartsWith([IO.Path]::GetFullPath($dir) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
  throw "The transcript must be inside the vault's Transcripts folder."
}
if (-not (Test-Path -LiteralPath $src)) { throw "Not found: $src" }

$turns = New-Object System.Collections.Generic.List[object]
$time = ""
foreach ($line in Get-Content -LiteralPath $src -Encoding UTF8) {
  $l = $line.Trim()
  if (-not $l -or $l -eq "WEBVTT" -or $l -like "NOTE*") { continue }
  if ($l -match '^(\d{2}:)?\d{2}:\d{2}\.\d{3}\s+-->') {
    $t = ($l -split '\s+')[0]
    $time = $t.Substring(0, $t.Length - 4)
    continue
  }
  if ($l -match '^[0-9a-fA-F]{8}-[0-9a-fA-F-]+(/\d+-\d+)?$') { continue }
  $speaker = $null
  $text = $l
  if ($l -match '^<v ([^>]*)>(.*)$') { $speaker = $Matches[1].Trim(); $text = $Matches[2] }
  $text = ($text -replace '<[^>]+>', '').Trim()
  if (-not $text) { continue }
  if ($turns.Count -gt 0 -and (-not $speaker -or $speaker -eq $turns[$turns.Count - 1].Speaker)) {
    $turns[$turns.Count - 1].Text += " " + $text
  } else {
    $turns.Add([pscustomobject]@{ Speaker = $(if ($speaker) { $speaker } else { "Unknown" }); Time = $time; Text = $text })
  }
}
if ($turns.Count -eq 0) { throw "No speech found in $src" }

$safe = ($Title -replace '[\\/:*?"<>|]', '-').Trim()
if (-not (Test-Path -LiteralPath $work)) { [void](New-Item -ItemType Directory -Path $work) }
$out = Join-Path $work "$Date $safe transcript.md"
$body = New-Object System.Text.StringBuilder
[void]$body.AppendLine("---")
[void]$body.AppendLine("tags: [transcript]")
[void]$body.AppendLine("date: $Date")
[void]$body.AppendLine("source: $([IO.Path]::GetFileName($src))")
[void]$body.AppendLine("---")
[void]$body.AppendLine("# $safe — transcript, $Date")
[void]$body.AppendLine("")
foreach ($t in $turns) {
  [void]$body.AppendLine("**$($t.Speaker)** ($($t.Time)): $($t.Text)")
  [void]$body.AppendLine("")
}
[IO.File]::WriteAllText($out, $body.ToString(), $utf8)
"Wrote $out ($($turns.Count) turns)"
