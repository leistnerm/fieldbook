<#
Quick capture: pops up a one-line box and appends what you type to the
vault's Inbox.md as "- YYYY-MM-DD HH:mm <text>". Enter saves, Esc cancels.
Bound to a Windows hotkey by the shortcut SETUP.md creates.
#>
$ErrorActionPreference = "Stop"
$vault = Split-Path (Split-Path $PSScriptRoot)
$inbox = Join-Path $vault "Inbox.md"

Add-Type -AssemblyName System.Windows.Forms, System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$form = New-Object Windows.Forms.Form -Property @{
  Text = "Inbox"; Width = 540; Height = 120; TopMost = $true
  StartPosition = "CenterScreen"; FormBorderStyle = "FixedDialog"
  MaximizeBox = $false; MinimizeBox = $false; KeyPreview = $true
}
$box = New-Object Windows.Forms.TextBox -Property @{
  Left = 12; Top = 12; Width = 500; Font = New-Object Drawing.Font("Segoe UI", 11)
}
$hint = New-Object Windows.Forms.Label -Property @{
  Left = 12; Top = 48; Width = 500; Text = "Enter to save, Esc to cancel"
}
$form.Controls.AddRange(@($box, $hint))
$form.Add_KeyDown({
  if ($_.KeyCode -eq "Enter") { $_.SuppressKeyPress = $true; $form.Tag = $box.Text; $form.Close() }
  elseif ($_.KeyCode -eq "Escape") { $form.Close() }
})
$form.Add_Shown({ $form.Activate(); $box.Focus() })
[void]$form.ShowDialog()

$text = [string]$form.Tag
if ([string]::IsNullOrWhiteSpace($text)) { exit }
$line = "- {0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm"), ($text -replace "\s+", " ").Trim()

# Start on a new line if the file doesn't end with one; UTF-8 without BOM.
$prefix = ""
if (Test-Path $inbox) {
  $bytes = [IO.File]::ReadAllBytes($inbox)
  if ($bytes.Length -and $bytes[-1] -ne 10) { $prefix = "`n" }
}
[IO.File]::AppendAllText($inbox, "$prefix$line`n", (New-Object Text.UTF8Encoding $false))
