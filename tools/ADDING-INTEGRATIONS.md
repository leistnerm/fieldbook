# Adding an integration

Every remote integration must be configurable and testable from the common CLI.
Do not ship a provider with only a sync tool and no connection diagnostics.

1. Register its stable provider ID in the configuration provider list, fields,
   feature validation and pristine seeds. Include its credential-store namespace,
   protected config, notebook-readable config, updater backfill and starter checks.
   The guided menu and `--test all` enumerate the shared CLI provider list; do not
   add a separate test-only registry or silently exclude a new provider.
2. Implement `check_integration(root, provider, instance, ...)` in the diagnostics
   dispatch. Return sanitized provider/instance, `ok`, and stage/status/message
   entries. Distinguish URL reachability, credential acceptance and an authenticated
   read of the selected scope. An empty valid result can pass. Missing configuration,
   missing scope, unsupported checks and unavailable reads must stay unverified or
   fail, never green. Identity endpoints may be optional when a protected scoped
   read proves authentication. Never probe write endpoints to test permissions.
3. Reuse bounded HTTPS transport, fixed read-route allowlists, trusted-origin
   checks, response limits and sanitized errors. Query-only POST routes need an
   explicit allowlist. Do not follow remote URLs with credentials or expose tokens,
   response bodies, attendee data or private note content in test results.
4. Add bounded discovery and local record bindings where the integration supports
   project/course/calendar-like scopes. Preserve instance identity, custom note
   fields, bodies and default connection scopes; use the shared preview/backup and
   stale-file checks. If a capability does not exist, explain that explicitly.
5. Add the human setup requirements to the guided menu and user guide. Opening help
   must remain offline. Sign-in, credential access and remote tests require explicit
   menu actions; diagnostics may test a disabled feature without enabling it.
   New adapters use the same local-write approvals and remain remotely read only.
   Add a complete provider entry to `tools/integration-guides.json`: simple steps,
   supported credential/app types, minimal read scopes, exact Fieldbook field mapping,
   policy/administrator cases and verified official links. Update the checked date.
   The guide loader requires an entry for every registered provider. Add any new
   official host explicitly to its allowlist; never derive browser destinations
   from user input or a service response. Opening a link requires selecting it.
6. Add fixture tests for successful authenticated empty reads, invalid credentials,
   inaccessible/missing scopes, malformed/oversized responses, redirects, timeouts,
   partial results, redaction and no vault mutation. Exercise the common guided menu
   and test-all dispatch. Test real adapter code with injected HTTP/credential
   dependencies; do not substitute a happy-path stub for adapter-level coverage.
   Walk every credential-guide variant offline, including direct and menu entry,
   next/back/cancel and explicit link selection. Assert no credential access or
   vault mutation, and that the guide never labels an untested connection verified.
7. Update docs, cheat sheet, activation/upgrader tests, manifest and all starters.
   Record live account/platform acceptance separately from mocked test results.

CLI exit codes remain 0 for verified required reads, 1 for failures, and 2 for
incomplete/all-skipped results. Optional unknown checks must not mask a required
unverified scope. Keep stable IDs and report unsupported behavior rather than
claiming that an API key or a provider homepage response proves the full connection.
