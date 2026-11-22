# Security policy

## Reporting a vulnerability

Please report security issues privately through GitHub's **Report a vulnerability**
(Security tab) on this repository. Do not open a public issue, and never attach a real
CAS statement or any personal data. We aim to acknowledge reports within 3 working days.

## What TrailCut protects

- Uploaded PDFs and passwords are processed in memory only and never logged or stored.
- PAN, email, phone, address, nominees and folio numbers are dropped or masked before
  anything is kept in a session or sent to the AI model.
- Sessions expire 30 minutes after last use and can be deleted at once.
- Uploads are limited to PDFs under 10 MB; requests are rate limited per client.
- Responses carry strict security headers; CORS is limited to the web origin.
- Text from statements is treated as data, never as instructions to the AI.

## Scope

In scope: the API, the web app, ingestion, the agent layer and the default deployment
configuration in this repository. Out of scope: third-party services (AMFI, Anthropic,
hosting providers) and social engineering.
