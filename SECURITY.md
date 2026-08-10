# Security policy

## Reporting a vulnerability

Please use GitHub's private **Report a vulnerability** security-advisory flow. Do not open a public issue containing credentials, activity data, GPS traces, private API responses, or reproduction files from a real account.

Include only synthetic examples and the smallest code excerpt necessary to explain the issue.

## Supported versions

This project is currently alpha software. Security fixes target the latest commit on the default branch.

## Credential model

- Strava uses OAuth with the minimal `activity:read_all` scope required to read private activities selected by the account owner.
- Garmin authentication is handled by the community `garminconnect` client. The account password is not saved by NRC Volt Sync; session tokens are persisted locally.
- Runtime secrets never belong in Git, environment screenshots, issue bodies, or CI variables for this project.

## Threat boundaries

NRC Volt Sync does not protect against a user account or Mac that is already compromised. A process running as the same macOS user may be able to read the local Application Support folder. Keep FileVault enabled, use a protected user account, and do not run untrusted code under the same account.

## Dependency and provider risk

Garmin upload uses an unofficial client for a private API. Provider changes, authentication challenges, or rate limits can affect availability. Pin and review dependency updates, and validate one activity before any historical backfill.
