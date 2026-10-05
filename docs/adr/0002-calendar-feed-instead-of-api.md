# Read Canvas through the Calendar Feed, not the REST API

The student's school has disabled personal access tokens, and the Canvas REST API needs one. So the sync reads the student's Calendar Feed (Canvas → Calendar → Calendar Feed), an official, student-facing iCal subscription that needs no token. We rejected reusing the Canvas mobile app's token or logging in with a browser session: both work around a security control the school chose deliberately, and SSO or MFA would break them in CI anyway.

Supersedes [ADR 0001](./0001-assignments-api-over-planner.md).

## Consequences

- The feed has no submission or grade status. The sync never closes tasks; the user finishes Synced Tasks themselves.
- Undated Assignments, points possible and published/locked flags are unavailable.
- A due date removed in Canvas looks the same as a deleted Assignment: either way it becomes Missing from Canvas.
- Course and assignment IDs come from each event's Canvas link or UID, and the course code from the event title, so the parsing is tied to a format Canvas doesn't document.
- The feed address is the only Canvas secret. It doesn't expire, so retirement relies on the Sync End Date.
- If the school ever grants a token, the API path can come back as a follow-up that adds closing tasks when Assignments are Done.
