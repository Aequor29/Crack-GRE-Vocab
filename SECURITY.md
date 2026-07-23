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

## Exposed credentials

Credentials found in Git history must be treated as compromised. Removing a
secret from the current tree is not a substitute for rotating or revoking it.

When a credential is discovered:

1. Revoke or rotate it at the provider before relying on any repository cleanup.
2. Replace it in the deployment secret store and verify the service still works.
3. Record the provider, affected environment, rotation time, and verifier in the
   private incident record. Never record the secret itself.
4. Scan both the current tree and the complete reachable Git history:

   ```bash
   scripts/scan-secrets.sh current
   scripts/scan-secrets.sh history
   ```

The history scan may continue to report an already-rotated value. History
rewrites are a separate, coordinated incident-response decision because they
invalidate existing clones and commit references. They must not delay rotation.

## Deployment trust boundaries

`TRUST_X_FORWARDED_PROTO` defaults to false. Enable it only when Django is
deployed behind a trusted proxy that removes client-supplied
`X-Forwarded-Proto` values and sets the header itself.

`SECURE_HSTS_INCLUDE_SUBDOMAINS` also defaults to false. Enable it only after
every subdomain has been inventoried and confirmed HTTPS-only.
