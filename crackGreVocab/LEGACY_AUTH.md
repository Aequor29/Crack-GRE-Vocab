# Legacy authentication boundary

The current API uses Simple JWT bearer tokens. The following behavior is
intentionally preserved while AEQ-9 introduces server-managed sessions:

- `POST /vocab/signup/` returns `access` and `refresh` tokens.
- `POST /vocab/token/` issues a token pair.
- `POST /vocab/token/refresh/` refreshes an access token.
- Protected API requests send the access token as a bearer token.
- The existing frontend stores those tokens in browser local storage.

This is characterization, not the target security design. New authentication
features must not expand this JWT/local-storage surface. AEQ-9 owns the
replacement with secure, HTTP-only server-managed session cookies, CSRF
protection, Google OAuth, and the corresponding frontend migration. Remove this
document and the characterization tests only when that migration is complete.
