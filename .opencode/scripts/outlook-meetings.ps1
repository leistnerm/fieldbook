<#
Lists meetings from your classic Outlook calendar, with attendees, as JSON.
Read-only: it never changes anything in Outlook. Needs classic Outlook
running (not new Outlook, not run as administrator).

  powershell -NoProfile -ExecutionPolicy Bypass -File outlook-meetings.ps1
  ... -Date 2026-10-01 -Days 3     a range instead of today
  ... -Test                        counts only, no names or subjects
#>
param(
  [datetime]$Date = (Get-Date).Date,
  [int]$Days = 1,
  [switch]$Test
)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$PR_SMTP = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
$RESPONSE = @{ 0 = "none"; 1 = "organizer"; 2 = "tentative"; 3 = "accepted"; 4 = "declined"; 5 = "not responded" }
$MEETING = @{ 0 = "not a meeting"; 1 = "organized by me"; 3 = "received"; 5 = "cancelled (mine)"; 7 = "cancelled" }
$ROLE = @{ 1 = "required"; 2 = "optional"; 3 = "resource" }

function Get-Attendee($recipient) {
  $p = [ordered]@{
    name = $recipient.Name; email = $null; kind = "unknown"
    role = $ROLE[[int]$recipient.Type]; response = $RESPONSE[[int]$recipient.MeetingResponseStatus]
    title = $null; department = $null; company = $null; manager = $null
  }
  if ($recipient.Type -eq 3) { $p.kind = "room" }
  $entry = $null
  try { $entry = $recipient.AddressEntry } catch {}
  if (-not $entry) { $p.email = $recipient.Address; return $p }
  $type = [int]$entry.AddressEntryUserType
  if ($type -in 1, 20) {
    # Distribution list
    $p.kind = "group"
    try { $p.email = $entry.GetExchangeDistributionList().PrimarySmtpAddress } catch {}
    return $p
  }
  $ex = $null
  if ($type -in 0, 5) { try { $ex = $entry.GetExchangeUser() } catch {} }
  if ($ex) {
    if ($p.kind -ne "room") { $p.kind = "directory" }
    $p.name = $ex.Name
    $p.email = $ex.PrimarySmtpAddress
    $p.title = $ex.JobTitle
    $p.department = $ex.Department
    $p.company = $ex.CompanyName
    try { $m = $ex.GetExchangeUserManager(); if ($m) { $p.manager = $m.Name } } catch {}
  } else {
    if ($p.kind -ne "room") { $p.kind = "external" }
    try { $p.email = $entry.PropertyAccessor.GetProperty($PR_SMTP) } catch {}
    if (-not $p.email) { $p.email = $entry.Address }
  }
  return $p
}

$clock = [Diagnostics.Stopwatch]::StartNew()
try {
  $outlook = New-Object -ComObject Outlook.Application
} catch {
  Write-Error "Couldn't reach Outlook: $($_.Exception.Message). Is classic Outlook open, and not running as administrator?"
  exit 1
}
$calendar = $outlook.GetNamespace("MAPI").GetDefaultFolder(9) # 9 = calendar
$items = $calendar.Items
# Order matters: sort by start, then expand recurring meetings, then filter.
$items.Sort("[Start]")
$items.IncludeRecurrences = $true
$from = $Date.Date
$to = $from.AddDays($Days)
$filter = "[Start] < '{0}' AND [End] > '{1}'" -f $to.ToString("g"), $from.ToString("g")
$found = $items.Restrict($filter)

$meetings = @()
$privateSkipped = 0
$item = $found.GetFirst()
while ($null -ne $item) {
  if ($item.Sensitivity -eq 2) {
    # Private meetings are never read into the vault.
    $privateSkipped++
  } elseif ($item.MeetingStatus -notin 5, 7) {
    # (5 / 7 = cancelled meeting, skipped)
    $attendees = @()
    $recipientError = $null
    try {
      $list = $item.Recipients
      if ($null -eq $list) {
        $recipientError = "Recipients came back empty"
      } else {
        for ($i = 1; $i -le $list.Count; $i++) {
          $attendees += [pscustomobject](Get-Attendee $list.Item($i))
        }
      }
    } catch {
      $recipientError = $_.Exception.Message
    }
    $required = $null
    try { $required = $item.RequiredAttendees } catch {}
    $meetings += [pscustomobject][ordered]@{
      subject    = $item.Subject
      start      = $item.Start.ToString("yyyy-MM-dd HH:mm")
      end        = $item.End.ToString("yyyy-MM-dd HH:mm")
      allDay     = [bool]$item.AllDayEvent
      location   = $item.Location
      organizer  = $item.Organizer
      recurring  = [bool]$item.IsRecurring
      myResponse = $RESPONSE[[int]$item.ResponseStatus]
      meetingStatus = $MEETING[[int]$item.MeetingStatus]
      categories = $item.Categories
      attendees  = $attendees
      recipientError = $recipientError
      requiredText   = $required
    }
  }
  $item = $found.GetNext()
}

if ($Test) {
  "Outlook OK (version {4}). {0} meeting(s) from {1:yyyy-MM-dd} for {2} day(s), in {3:N1}s." -f $meetings.Count, $from, $Days, $clock.Elapsed.TotalSeconds, $outlook.Version
  # Diagnostics for attendee access: Outlook's address-book protection
  # ("object model guard") and any company policy that sets it.
  foreach ($key in "HKCU:\Software\Policies\Microsoft\Office\16.0\Outlook\Security",
                   "HKLM:\SOFTWARE\Policies\Microsoft\Office\16.0\Outlook\Security",
                   "HKLM:\SOFTWARE\Microsoft\Office\16.0\Outlook\Security") {
    $v = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
    if ($v) {
      $names = "ObjectModelGuard", "PromptOOMAddressInformationAccess", "PromptOOMAddressBookAccess", "AdminSecurityMode"
      $found = foreach ($n in $names) { if ($null -ne $v.$n) { "$n=$($v.$n)" } }
      "policy {0}: {1}" -f $key, $(if ($found) { $found -join ", " } else { "(none of the guard settings)" })
    }
  }
  "{0} private meeting(s) skipped; by status: {1}" -f $privateSkipped, (($meetings | Group-Object meetingStatus | ForEach-Object { "$($_.Name) $($_.Count)" }) -join ", ")
  $errs = @($meetings | Where-Object recipientError)
  "attendee access: {0} meeting(s) with an error; required-attendees text readable on {1} of {2}" -f $errs.Count, @($meetings | Where-Object requiredText).Count, $meetings.Count
  if ($errs.Count) { "first error: {0}" -f $errs[0].recipientError }
  foreach ($m in $meetings) {
    $a = $m.attendees
    $people = @($a | Where-Object { $_.kind -in "directory", "external", "unknown" })
    $dir = @($a | Where-Object kind -eq "directory")
    "{0}-{1}  {2,-9} {3,-14} attendees {4,2}: directory {5}, external {6}, group {7}, room {8} | email {9}/{10} | dept {11}/{12} | company {13}/{12} | manager {14}/{12}" -f `
      $m.start.Substring(11), $m.end.Substring(11),
      $(if ($m.recurring) { "recurring" } else { "one-off" }), $m.myResponse, $a.Count,
      $dir.Count, @($a | Where-Object kind -eq "external").Count,
      @($a | Where-Object kind -eq "group").Count, @($a | Where-Object kind -eq "room").Count,
      @($people | Where-Object email -like "*@*").Count, $people.Count,
      @($dir | Where-Object department).Count, $dir.Count,
      @($dir | Where-Object company).Count, @($dir | Where-Object manager).Count
  }
} else {
  ConvertTo-Json -InputObject @($meetings) -Depth 5
}
