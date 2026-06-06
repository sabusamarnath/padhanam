# P16 / S60c — Real Google OIDC sign-in against the operator's OAuth client (procedural smoke)

S60c wires the real Google **OpenID Connect** login behind the existing
`LoginVerifier` port (D161): sign in with `operator@example.com`, the
callback resolves the email to the personal tenant and mints the platform JWT
the data routes already require, and you land in the app shell as that tenant.
**Gate-enabling, not a new value surface** — the dogfooding-login unblock.

Operator-driven and operator-gated (AC6). Google's live token contract is
reconciled **here**, not asserted from memory (the S4/S55a-fix discipline): the
build environment cannot reach Google or a browser, so the verifier raises
until the OAuth client is configured and the live run is the operator's.

- **Login carries identity scopes only** (`openid email profile`). Calendar and
  mail **data** stay on the separate Nango path (D148). **Signing in is not the
  same as the data flowing** — Today stays empty of calendar events until the
  S60b Nango connect runs.

Personal tenant: `00000000-0000-4000-8000-00000000d001` (tag `dogfood-stable`).
Callback path (intended): `http://localhost:8000/api/v1/auth/google/callback`.

---

## Operator-manual pre-flight (do these before the live run)

1. **Authorized redirect URI.** On the Google OAuth client (Google Cloud
   console → APIs & Services → Credentials → your OAuth 2.0 Client ID), add
   `http://localhost:8000/api/v1/auth/google/callback` to **Authorized redirect
   URIs**. This must match `GOOGLE_OAUTH_REDIRECT_URI` exactly (scheme, host,
   port, path). If your stack publishes the API on a different origin, set both
   to that origin.

2. **Test user.** On the OAuth consent screen, confirm `operator@example.com`
   is listed as a **test user** (auto-allowed if it owns the project, but list
   it explicitly so the unverified-app screen lets it through).

3. **`.env` (gitignored — secret + email never committed).** Set:

   ```env
   LOGIN_BACKEND=google
   GOOGLE_OAUTH_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
   GOOGLE_OAUTH_CLIENT_SECRET=<your-client-secret>
   GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/auth/google/callback
   GOOGLE_OAUTH_EMAIL_TO_TENANT={"operator@example.com": "00000000-0000-4000-8000-00000000d001"}
   ```

   (If reconciliation changed the callback path in Step 0, update the redirect
   URI in both the console and `.env` to match.)

4. **Restart the API** so settings + the boot-time wiring pick up the OAuth
   client:

   ```bash
   docker compose restart padhanam-api
   ```

---

## Stage 0 — bring the code up and confirm the routes mount

```bash
make sync-code   # or build-api + recreate for the boot-time router/static pickup
docker compose restart padhanam-api
```

Confirm the Google routes are mounted and the OIDC client is wired (not gated):

```bash
docker compose exec padhanam-api python -c \
 "import apps.api.routers.auth as a; \
  print([r.path for r in a.router.routes])"
# Expect /api/v1/auth/google/initiate and /api/v1/auth/google/callback present.

docker compose exec padhanam-api python -c \
 "from padhanam.config import GoogleOAuthSettings as G; s=G(); \
  print('configured=', s.is_configured); \
  print('mapped=', bool(s.google_oauth_email_to_tenant))"
# Expect configured= True and mapped= True.
```

If `configured= False`, the client id/secret are not reaching the container —
re-check `.env` and the restart. While unconfigured, `/google/initiate` and
`/google/callback` return **503** (operator-gated, by design).

---

## Stage 1 — the live sign-in (AC1, AC2, AC6)

1. Open `http://localhost:8000/login` in a browser.
2. Click **Continue with Google**. The browser redirects to Google's consent
   screen (AC1 — the initiate route started the OIDC flow). If you see an
   "unverified app" / "Google hasn't verified this app" warning, click
   **Advanced → Go to … (unsafe)** — expected for a testing-mode client.
3. Choose / sign in as `operator@example.com` and grant the
   `openid email profile` consent.
4. Google redirects back to `/api/v1/auth/google/callback?code=…&state=…`. The
   callback verifies the ID token, resolves the email to the personal tenant,
   mints the JWT, and the bridge page lands you in **`/app`** as the personal
   tenant (AC2, AC6).

**Record:** ☐ landed in the app shell signed in as `operator@example.com`,
scoped to `00000000-0000-4000-8000-00000000d001`.

Confirm the session is the personal tenant's (the rail / account control shows
the operator; the Today surface reads the personal tenant's items).

---

## Stage 2 — the data routes authorize with the Google-minted session (AC4)

With the browser still signed in (the token is in `localStorage['dd_token']`),
confirm a data route authorizes exactly as it does for the passphrase login —
e.g. the Today list and Connections status load without a 401. In the browser
devtools Network tab, a `/api/v1/daily-driver/...` request carries
`Authorization: Bearer <dd_token>` and returns 200.

**Record:** ☐ data routes return 200 with the Google-minted bearer (no re-auth,
no 401) — byte-identical to the passphrase-minted session.

---

## Stage 3 — the reject paths (AC3)

1. **Unmapped email.** Temporarily sign in (or attempt to) with a Google
   account **not** in `GOOGLE_OAUTH_EMAIL_TO_TENANT`. The callback returns to
   `/login` showing "no tenant mapped for …"; **no session is minted**
   (`localStorage['dd_token']` is unchanged / absent). Restore the operator
   account afterward.

**Record:** ☐ an unmapped email is rejected cleanly — no tenant fabricated, no
`dd_token` written.

---

## Stage 4 — what is NOT proven here (honest scope)

- **The data is not flowing.** Login carries identity scopes only; the Today
  surface stays empty of calendar events until the S60b Nango connect runs
  (`docs/smoke/p16_s60b_live_connect.md`). Signing in ≠ data flowing.
- **Apple / Microsoft Entra / SCIM / enterprise SSO** are the parallel identity
  package — not in scope here.
- **Production identity** stays the Keycloak swap (D3/D23); this is the
  dogfooding-stack login adapter.

---

## Acceptance criteria checklist

- ☐ AC1 — "Continue with Google" starts the OIDC flow at the initiate route.
- ☐ AC2 — the callback verifies a valid ID token, resolves the email to the
  personal tenant, mints the JWT, lands in the authenticated state.
- ☐ AC3 — an unmapped email is rejected cleanly (no tenant, no session).
- ☐ AC4 — data routes authorize with the Google-minted session as with the
  passphrase-minted one.
- ☐ AC5 — tests pass from cleared bytecode with Google mocked; import-linter +
  AST green; no vendor SDK in domain code. *(Verified in-build: 2278 passed,
  +34 S60c; 42 contracts; 9 enforcement. The one suite failure is a
  pre-existing wall-clock-coupled calendar test, unrelated — `log/captures.md`
  [S60c].)*
- ☐ AC6 — **operator-gated live run:** signed in with `operator@example.com`,
  past the unverified-app warning, into the app shell as the personal tenant.
