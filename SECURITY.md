# Security Policy

## Reporting a vulnerability

Please do not disclose suspected vulnerabilities in a public issue.

Use GitHub private vulnerability reporting when it is enabled for this
repository. Otherwise, contact the repository owner privately through their
GitHub profile and include reproduction steps, affected versions, and potential
impact.

## Exposed credentials

Credentials found in Git history must be treated as compromised. Removing a
secret from the current tree is not a substitute for rotating or revoking it.

When a credential is discovered:

1. Revoke or rotate it at the provider.
2. Replace it in the deployment secret store and verify the service still works.
3. Record the provider, environment, rotation time, and verifier in a private
   incident record. Never record the secret itself.
4. Scan the current tree and full Git history with an established secret scanner.

History cleanup is a separate, coordinated incident-response decision and must
not delay rotation.
