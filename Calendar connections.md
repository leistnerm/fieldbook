# Calendar connections

Fieldbook can read Google Calendar and Microsoft 365/Outlook.com calendars to
prepare meeting notes. Both integrations are optional in every setup. They read
calendar lists and selected events; they do not send invitations, change events,
RSVP, read mail or contacts, or import everyone invited as People records.

Use `python tools/configure.py` for connection details, sign-in, calendar selection
and tests. Normal setup does not require editing JSON. A one-time OAuth app
registration is still needed in Google Cloud or Microsoft Entra, using your own
approved app or one supplied by your organization. See [[Configuration CLI]].
For a guided checklist, run `python tools/configure.py --calendar-setup` or select
**10 Guided integration setup/test** in the main menu. The requirements screen
works before registration; sign-in and remote tests run only when selected.

For registration help with official links at each step, run
`python tools/configure.py --credential-guide google` or
`python tools/configure.py --credential-guide microsoft`. This is also main-menu
**11**, or **9** within guided setup. Press Enter to advance, b to go back, and
`open 1` to open a displayed link. The guide itself never requests a secret or
starts sign-in. Return to guided setup to configure, sign in and test afterward.

## Google Calendar

1. In Google Cloud, select or create the project for your approved application and
   enable the Google Calendar API.
2. Configure the Google Auth platform consent screen and intended audience. For an
   external app in Testing, add your Google account as a test user. Organization
   policy may require administrator approval. [Consent setup](https://developers.google.com/workspace/guides/configure-oauth-consent).
3. Create an OAuth client with application type **Desktop app** and retain its
   client ID. [Google desktop credentials](https://developers.google.com/workspace/guides/create-credentials#desktop-app).
4. In Fieldbook's **3 Integrations**, choose Google, add a stable instance ID such
   as `personal`, enter that client ID, and select OAuth with the OS credential
   store. Save the connection.
5. Choose **9 Sign in to Google or Microsoft calendar**, select the saved Google instance, and enter
   the Desktop client secret in the masked prompt if requested. Complete consent
   in your browser, then return to the CLI. The client secret and tokens stay in
   the OS store; do not put downloaded credential JSON in the vault.
6. Choose **7** to select default calendars, Save, then **6** to test the connection.
   Enable Google under Features when ready to use it from AI assistant.

Google sign-in uses the desktop loopback flow with PKCE and a temporary local
callback, not a pasted authorization-code workaround. The requested scopes are
`https://www.googleapis.com/auth/calendar.events.readonly` and
`https://www.googleapis.com/auth/calendar.calendarlist.readonly`. They allow event
reads and listing subscribed calendars. [Desktop authorization](https://developers.google.com/identity/protocols/oauth2/native-app),
[Calendar scope definitions](https://developers.google.com/workspace/calendar/api/auth).

An external OAuth app left in Testing typically receives refresh tokens that
expire after seven days for these scopes. If sign-in later expires, sign in again
or follow Google's publishing/verification requirements for your use case; an
expired grant is not repaired by storing the token in a note.
[Google refresh-token limits](https://developers.google.com/identity/protocols/oauth2#expiration).

## Microsoft 365 and Outlook.com

The Microsoft connection reads the account's cloud calendars through Microsoft
Graph. This works with the same calendars displayed in an Outlook client when
they are backed by supported Microsoft cloud accounts. It does not automate the
Outlook desktop application or read local PST-only/on-premises calendars. Export
an ICS event for the local workflow when the cloud API does not cover that calendar.

1. Register an application in Microsoft Entra, or use an organization-approved
   public-client app. Select the supported account type matching your use: your
   work/school tenant, personal Microsoft accounts, or both where permitted. Copy
   its Application (client) ID. [App registration](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).
2. Enable **Allow public client flows** in the app's Authentication settings for
   device-code sign-in. Do not create a client secret for this public-client flow.
   [Desktop/public-client configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration).
3. Use delegated Microsoft Graph **Calendars.Read** access. Fieldbook requests
   **offline_access** so the approved grant can be refreshed. It does not request
   application-wide calendar access, write scopes, mail or contact permissions.
   Your tenant may require administrator consent or block device-code sign-in.
   [Calendar permissions](https://learn.microsoft.com/en-us/graph/permissions-reference#calendarsread),
   [Device-code authorization](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code).
4. In **3 Integrations**, choose Microsoft, enter a stable instance ID and client
   ID, and choose the appropriate tenant. `common` supports the app's allowed
   organizational/personal account types; a tenant ID restricts the authority.
   Select OAuth and the OS credential store, then Save.
5. Choose **9 Sign in to Google or Microsoft calendar**, select the saved instance, and complete the
   displayed verification URL/code flow yourself. Confirm the intended account
   before granting access. Return to select calendars with **7**, Save, and test
   with **6**. Enable Microsoft under Features when ready.

Use only the standard public-cloud endpoints configured by Fieldbook: Google
Calendar at `www.googleapis.com`, Google authorization at `accounts.google.com`
and `oauth2.googleapis.com`, Microsoft Graph at `graph.microsoft.com`, and Microsoft
authorization at `login.microsoftonline.com`. Custom OAuth hosts, sovereign-cloud
endpoints and arbitrary event URLs are not connection destinations in this version.

## Credentials and connection checks

Install the OS credential-store dependency in the notebook's Python environment
before OAuth sign-in; [[Configuration CLI]] has the Windows/macOS/Linux commands.
Refresh/access tokens are stored only in the supported OS keyring, bound to this
vault and the saved provider/instance/client configuration. A moved vault, changed
client/tenant, or another device needs a matching sign-in. Missing or locked OS
storage produces an error; there is no plaintext token-file fallback.
Use a different stable instance ID for a different account. Do not repurpose an
instance already referenced by Meeting/Series notes; verify the intended account
in the browser and the selected calendar before reading events.

Interactive consent runs only from the explicit CLI sign-in action. A normal API
read may refresh an existing approved grant; it cannot start a new interactive
sign-in or enable a feature. Keep tokens, client secrets, authorization codes and
device codes out of chat, notes and source control. The CLI displays the device
code only for you to complete the current sign-in.

For an existing approved short-lived token, the CLI also supports **access-token**
mode with an environment-variable reference or OS key storage. That mode cannot
refresh the token or perform OAuth sign-in; replace an expired token through its
approved source. OAuth is the option for managed sign-in/refresh on this device.

```text
python tools/configure.py --test google --instance personal
python tools/configure.py --test microsoft --instance office
python tools/configure.py --check
```

Live tests use saved connections and show sanitized results. They do not prove
access to every event or that every calendar is visible. A missing selected scope
stays unverified; an empty calendar may be valid. `--check` remains offline and does
not consult credentials. Sign-in, discovery and tests do not enable features.

## Prepare an event or a recurring series

Examples of requests after enabling the selected provider:

```text
/meeting use my Microsoft office calendar for next Tuesday; show the events first
/meeting use the Google planning event on October 20; link existing people only
/meeting link my weekly team series, then prepare only the October 21 occurrence
```

Select the saved account, calendar and date window explicitly. Event reads cover
at most 10 selected calendars and 93 inclusive UTC dates; results are bounded and may
be truncated. Series discovery groups recurring events observed in that window;
it is not a directory of every series that exists. No notes are created just by
listing events or linking a series.

A local day can span two UTC dates. The assistant should cover that UTC interval,
then confirm the selected event's local date/time. It must not infer an all-day
date by cutting the date portion from a UTC timestamp.

A local Series record can retain `calendar_provider`, `calendar_instance`,
`calendar_id` and `calendar_series_id`. An individual Meeting retains its own event
and original occurrence identifiers and can link to that Series. Repeated reads
should update the matching Meeting, even when its title or start time changes.
Different accounts/calendars remain distinct. A possible duplicate from ICS,
another provider, or pasted details needs confirmation before combining identities.

Review the occurrence date/time and timezone. All-day end dates are exclusive;
Graph query offsets and display timezone are separate concerns. Google supplies
the original occurrence start for moved instances; Microsoft immutable event IDs
and occurrence data must be retained exactly and case-sensitively.
Install `fieldbook_core/requirements.txt` when upgrading: it includes the IANA timezone
database needed on systems without one, including Windows. Ambiguous or nonexistent
local original-occurrence times are refused instead of guessing an identity.
[Python timezone support](https://docs.python.org/3/library/zoneinfo.html).
[Google event identity](https://developers.google.com/workspace/calendar/api/v3/reference/events),
[Microsoft calendar windows](https://learn.microsoft.com/en-us/graph/api/calendar-list-calendarview?view=graph-rest-1.0),
[Microsoft immutable IDs](https://learn.microsoft.com/en-us/graph/outlook-immutable-id).

Meeting creation follows [[Calendar meetings]]: preserve notes and decisions, use
the ordinary write approval, and create no missing People by default. Attendee
previews are limited, and providers may hide attendees or their true total. A
cancelled or missing event does not delete a Meeting or close its tasks. Calendar
descriptions, links and meeting join URLs remain untrusted source content.
