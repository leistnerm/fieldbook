# Read-only checks over the vault's notes; changes nothing.
#   link-check.ps1             [[links]] that point at no note
#   link-check.ps1 -Mentions   people named in plain text but not linked
#                              (notes changed in the last -Since days, or -All)
param(
  [switch]$Mentions,
  [int]$Since = 14,
  [switch]$All
)
$ErrorActionPreference = "Stop"
$vault = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$skipDirs = @(".obsidian", ".opencode", ".git", ".trash", "node_modules")
# Frontmatter fields holding people: auto-people.js creates those notes.
$peopleFields = @("attendees", "assignee", "owner", "stakeholders", "deciders", "manager", "requester")

function Split-Note([string]$text) {
  $m = [regex]::Match($text, '^﻿?---\r?\n([\s\S]*?)\r?\n---[ \t]*(\r?\n|$)')
  if ($m.Success) { return @($m.Groups[1].Value, $text.Substring($m.Length)) }
  return @("", $text)
}

function Remove-Code([string]$s) {
  $s = [regex]::Replace($s, '(?ms)^(```|~~~).*?^\1', '')
  return [regex]::Replace($s, '`[^`\r\n]*`', '')
}

function Get-Aliases([string]$fm) {
  $out = @()
  $in = $false
  foreach ($line in ($fm -split '\r?\n')) {
    if ($line -match '^([A-Za-z_][\w-]*)\s*:(.*)$') {
      $in = ($Matches[1] -eq "aliases")
      if ($in) { $out += ($Matches[2] -replace '^\s*\[|\]\s*$', '' -split ',') }
    } elseif ($in -and $line -match '^\s*-\s*(.*)$') {
      $out += $Matches[1]
    }
  }
  return @($out | ForEach-Object { "$_".Trim().Trim('"').Trim("'") } | Where-Object { $_ })
}

function Get-Dist([string]$a, [string]$b) {
  $m = $a.Length
  $n = $b.Length
  if ([Math]::Abs($m - $n) -gt 3) { return 99 }
  $prev = @(0..$n)
  for ($i = 1; $i -le $m; $i++) {
    $cur = @($i) + @(0) * $n
    for ($j = 1; $j -le $n; $j++) {
      $cost = 1
      if ($a[$i - 1] -eq $b[$j - 1]) { $cost = 0 }
      $cur[$j] = [Math]::Min([Math]::Min($prev[$j] + 1, $cur[$j - 1] + 1), $prev[$j - 1] + $cost)
    }
    $prev = $cur
  }
  return $prev[$n]
}

# Every file in the vault, so links to Templates, attachments and views resolve.
$found = @(Get-ChildItem -LiteralPath $vault -File)
foreach ($d in (Get-ChildItem -LiteralPath $vault -Directory)) {
  if ($skipDirs -notcontains $d.Name) { $found += @(Get-ChildItem -LiteralPath $d.FullName -Recurse -File) }
}
$items = @($found | ForEach-Object {
  [pscustomobject]@{
    Path  = $_.FullName
    Rel   = $_.FullName.Substring($vault.Length).TrimStart('\')
    Name  = [IO.Path]::GetFileNameWithoutExtension($_.Name)
    Ext   = $_.Extension.ToLower()
    Mtime = $_.LastWriteTime
  }
})

# Names a link can resolve to: "Name", "Folder/Name", "Sub/Folder/Name" (no .md).
$known = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($f in $items) {
  $p = $f.Rel.Replace('\', '/')
  if ($f.Ext -eq ".md") { $p = $p.Substring(0, $p.Length - 3) }
  $parts = $p.Split('/')
  for ($i = 0; $i -lt $parts.Count; $i++) { [void]$known.Add((@($parts[$i..($parts.Count - 1)]) -join '/')) }
}

$notes = @()
foreach ($f in $items) {
  if ($f.Ext -ne ".md") { continue }
  $fm, $body = Split-Note ([IO.File]::ReadAllText($f.Path))
  $notes += [pscustomobject]@{ Item = $f; Name = $f.Name; Rel = $f.Rel; Fm = $fm; Body = $body }
}

if ($Mentions) {
  $owners = @{}
  foreach ($n in $notes) {
    if ($n.Fm -notmatch '(?m)^tags:.*\bperson\b|^\s*-\s*person\s*$') { continue }
    $keys = @(@($n.Name) + @(Get-Aliases $n.Fm) | ForEach-Object { ("$_" -replace '\s*\([^)]*\)\s*$', '').Trim() } | Where-Object { $_.Length -ge 4 } | Select-Object -Unique)
    foreach ($k in $keys) {
      if (-not $owners.ContainsKey($k)) { $owners[$k] = @() }
      if ($owners[$k] -notcontains $n.Name) { $owners[$k] += $n.Name }
    }
  }
  if ($owners.Count -eq 0) { "No person notes found."; exit 0 }
  $alt = (@($owners.Keys | Sort-Object { $_.Length } -Descending | ForEach-Object { [regex]::Escape($_) }) -join '|')
  $rx = [regex]::new('(?<![\w\[|/])(' + $alt + ')(?![\w\]|])', 'IgnoreCase')
  $cutoff = (Get-Date).AddDays(-$Since)
  $hits = @{}
  foreach ($n in $notes) {
    if ($n.Rel -like 'People\*' -or $n.Rel -like 'Templates\*') { continue }
    if (-not $All -and $n.Item.Mtime -lt $cutoff) { continue }
    $text = [regex]::Replace((Remove-Code $n.Body), '\[\[[^\]]*\]\]', '')
    foreach ($m in $rx.Matches($text)) {
      $k = $m.Value.ToLower()
      if (-not $hits.ContainsKey($k)) { $hits[$k] = @{ Who = @($owners[$m.Value] ); Src = @{} } }
      $hits[$k].Src[$n.Rel] = 1 + [int]$hits[$k].Src[$n.Rel]
    }
  }
  $scope = "notes changed in the last $Since days"
  if ($All) { $scope = "all notes" }
  if ($hits.Count -eq 0) { "No unlinked people mentions ($scope)."; exit 0 }
  "Unlinked people mentions ($scope):"
  foreach ($k in ($hits.Keys | Sort-Object)) {
    $h = $hits[$k]
    $who = ($h.Who -join " or ")
    if ($h.Who.Count -gt 1) { $who = "AMBIGUOUS: $who" }
    "$k  ->  $who"
    foreach ($s in ($h.Src.Keys | Sort-Object)) { "  $s  x$($h.Src[$s])" }
  }
  exit 0
}

# Spelling suggestions: every note name, and every alias (an alias is not a link target).
$pool = @{}
foreach ($n in $notes) {
  $pool[$n.Name] = $n.Name
  foreach ($a in (Get-Aliases $n.Fm)) { if (-not $pool.ContainsKey($a)) { $pool[$a] = $n.Name } }
}

$linkRx = [regex]'(!?)\[\[([^\]\|#\^]+)(?:[#\^\|][^\]]*)?\]\]'
$missing = @{}
function Add-Link($m, [string]$source, [string]$where) {
  $t = $m.Groups[2].Value.Trim().TrimEnd('\').Replace('\', '/')
  if (-not $t -or $t -match '<%|\{\{') { return }
  if ($known.Contains($t) -or $known.Contains(($t -replace '\.md$', ''))) { return }
  if (-not $missing.ContainsKey($t)) {
    $missing[$t] = [pscustomobject]@{ Target = $t; Count = 0; Sources = @{}; Fields = @{}; Embed = $false }
  }
  $e = $missing[$t]
  $e.Count++
  $e.Sources[$source] = 1
  $e.Fields[$where] = 1
  if ($m.Groups[1].Value -eq "!") { $e.Embed = $true }
}

foreach ($n in $notes) {
  if ($n.Rel -like 'Templates\*') { continue }
  $key = ""
  foreach ($line in ($n.Fm -split '\r?\n')) {
    if ($line -match '^([A-Za-z_][\w-]*)\s*:') { $key = $Matches[1] }
    if ($peopleFields -contains $key) { continue }
    foreach ($m in $linkRx.Matches($line)) { Add-Link $m $n.Rel "field $key" }
  }
  foreach ($m in $linkRx.Matches((Remove-Code $n.Body))) { Add-Link $m $n.Rel "body" }
}

if ($missing.Count -eq 0) { "No unresolved links."; exit 0 }
"Unresolved links: $($missing.Count) targets"
foreach ($e in ($missing.Values | Sort-Object -Property @{ Expression = "Count"; Descending = $true }, "Target")) {
  $last = $e.Target.Split('/')[-1]
  $embed = ""
  if ($e.Embed) { $embed = "  (embed)" }
  "[[$($e.Target)]]  x$($e.Count)$embed"
  $src = @($e.Sources.Keys | Sort-Object)
  $more = ""
  if ($src.Count -gt 6) { $more = " (+$($src.Count - 6) more)" }
  "  in: $((@($src | Select-Object -First 6)) -join ', ')$more"
  "  as: $((@($e.Fields.Keys | Sort-Object)) -join ', ')"
  if ($pool.ContainsKey($last)) {
    "  maybe: alias of [[$($pool[$last])]] (write [[$($pool[$last])|$last]])"
  } else {
    $best = $null
    $bd = 99
    foreach ($k in $pool.Keys) {
      $d = Get-Dist $last.ToLower() $k.ToLower()
      if ($d -lt $bd) { $bd = $d; $best = $k }
    }
    if ($best -and $bd -le [Math]::Max(2, [int]($last.Length / 5))) { "  maybe: typo of [[$($pool[$best])]]" }
  }
}
