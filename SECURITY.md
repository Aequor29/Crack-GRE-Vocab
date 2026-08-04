# Security Policy

## Reporting a vulnerability

Please do not disclose suspected vulnerabilities in a public issue.

Use GitHub private vulnerability reporting when it is enabled for this repository.
Otherwise, contact the repository owner privately through their GitHub profile
and include reproduction steps, affected versions, and potential impact.

The maintainer will acknowledge a report as soon as practical and coordinate a
fix and disclosure timeline with the reporter.

## Supported versions

This solo project supports only the latest version on the default branch.

## Retired prototype credentials

The current product is a private cold rebuild. Values from the retired prototype
must never be reused in a local, staging, or production environment. Milestone 1
does not recover old deployments, rewrite Git history, or perform provider
rotation work; pre-GA environments will receive entirely fresh credentials.

Any newly discovered credential that still grants access to an active,
non-prototype service should be reported privately and disabled through that
service's normal incident process.

## Deployment trust boundaries

`TRUST_X_FORWARDED_PROTO` defaults to false. Enable it only when Django is
deployed behind a trusted proxy that removes client-supplied
`X-Forwarded-Proto` values and sets the header itself.

`SECURE_HSTS_INCLUDE_SUBDOMAINS` also defaults to false. Enable it only after
every subdomain has been inventoried and confirmed HTTPS-only.
