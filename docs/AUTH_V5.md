# GRIDIRON AI account experience

The app account is a GRIDIRON AI identity. A person using the app never needs a Supabase dashboard account. Supabase Auth and PostgreSQL are infrastructure behind the server API.

## Cause of the old experience

The original home, NFL research, market and simulation APIs shared the private user gate. `middleware.ts` sent nearly every API request into the owner-required cloud handler, and the Settings interface described app identities as “a Supabase account.” This made public football research depend on personal sign-in and exposed an operator's database choices in the consumer interface.

The audited application sign-in did not redirect to a developer dashboard. Email/password authentication already happened through the GRIDIRON AI server. Email-confirmation URLs used the app origin, but the old implicit confirmation return did not establish the server's private session cookies automatically.

A safe, invalid-token redirect probe found an additional concrete operator configuration problem: the live Auth verification endpoint rejected both forms of the deployed app origin as a return destination and redirected to `http://localhost:3000/`. No real verification token or account was used, and no email was sent. The Auth redirect utility checks the requested destination and then falls back to its Site URL. The app's production origin must be configured as an allowed Auth return URL; changing application code does not bypass that security allowlist. The connected management tools do not expose a mutation for that setting. Existing confirmed-account password sign-in and guest NFL research remain independent of that email-return configuration.

## Public and private routes

`/api/nfl` and its game-analysis routes bypass the private owner handler. `/api/auth/providers` exposes only public enabled-provider booleans. `/api/auth/apple` starts the guarded identity flow. `/api/auth` retains the existing backend routing, and private financial, conversation, prediction and account endpoints still require independently verified identity and owner-scoped RLS.

The consumer interface offers guest research, an app sign-in modal when private records are needed, and an optional Advanced Mode. Legacy data selection and encrypted import remain available in Advanced Mode. Existing private records and authentication were not reset.

## Session and confirmation security

Email registration and optional Apple sign-in use a random PKCE verifier in a short-lived HttpOnly, Secure, SameSite=Lax app cookie. Only the SHA-256 challenge leaves the server during initiation. The identity provider returns a one-use code to the existing app origin. `AppAuthReturn` sends it to the internal `/auth/callback` handler, which exchanges it with the server-held verifier, independently verifies the returned user, and sets the existing private access/refresh cookies.

Callback redirects have fixed app destinations. A client-supplied `next` URL or access-token claim cannot select an identity or an external destination. Provider errors do not overwrite an existing valid session. Private responses are not cached. Confirmation is not disabled. If an email link is opened on a different device, the person can finish by signing into GRIDIRON AI with their confirmed email/password.

## Apple availability

The actual project Auth settings inspected on 2026-10-30 reported email enabled and Apple disabled. The app therefore does not display an unusable Apple button. The server rechecks enabled provider capabilities and rejects an unavailable Apple start.

To enable Apple, the operator must configure its web Services ID, authorized Apple return URL and Apple secret in the authentication provider, with the app origin permitted as a return URL. Those are operator credentials; users do not configure them. Apple web secrets require periodic renewal. No Apple consent or account-linking flow was tested against a real Apple identity in this environment.

## Verification boundary

The dedicated app-auth tests cover provider availability, disabled-provider rejection, PKCE challenge/cookie binding, cross-origin starts, callback verification, fixed return destinations, private cookie handling, registration confirmation, safe upstream errors and unchanged private API routing. Existing refresh/ownership tests continue to pass. Live email delivery and provider redirect configuration remain separate external checks; no emails were sent or security controls disabled for a test.
