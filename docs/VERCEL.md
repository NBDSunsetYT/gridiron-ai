# Vercel frontend and API deployment

The existing Next.js/React app stays intact. Vercel hosts its frontend and authenticated Node API; the separate Python/FastAPI service runs on Render. Supabase Auth/PostgreSQL remains the durable account database. No native IPA, App Store or TestFlight release is part of this deployment.

## Current verified account and scope

The connected Vercel user is on the **Hobby** plan. The user's default team scope is `gridiron5`, ID `team_GWp3QPUQgohJPqe7ppe9pYmS`. The initial scoped project request returned HTTP 403 with Vercel's explicit requirement to authorize team access. The native `authorize_team_access` flow was started; its one-use link must be approved by the account owner before using that scope. An installed connector does not itself prove access to every team. Do not create the project in a different personal/team scope to bypass that authorization requirement.

No project or deployment is claimed here until the actual native API result and production checks establish it. After authorization, reuse an existing GRIDIRON project if one appears rather than creating a duplicate.

## Build and runtime settings

- Framework: Next.js. Repository root: this application directory.
- Install: `npm ci`; build: `npm run build`; output directory: framework default.
- Node: supported 22.x or 24.x.
- Use Hobby/default build resources and Fluid Compute; no turbo build, paid memory or multiple-region upgrade is requested.
- `vercel.json` caps API functions at 300 seconds, the current Hobby Fluid Compute maximum. Route-level `maxDuration` exports must also remain at or below that limit.
- `.vercelignore` excludes local credentials, financial databases, caches and Python/native source from CLI uploads. It retains the three historical JSON reports actually imported by the web components.

Current official Vercel documentation states that **both request and response bodies are limited to 4.5 MB**. Increasing Next's middleware limit does not raise that gateway limit. Signed fitted artifacts can be larger. Use owned model-job references and compact server responses instead of resending or returning entire multi-megabyte artifacts in ordinary API JSON. A local Docker pass does not test this platform gateway constraint.

## Server environment

Configure these through the authorized Vercel project environment tools, with sensitive/encrypted values and production/preview targets as appropriate:

```text
DATA_BACKEND=supabase
GRIDIRON_CLOUD_ONLY=1
GRIDIRON_COMPACT_API=1
SUPABASE_URL=<existing gridiron-ai project URL>
SUPABASE_PUBLISHABLE_KEY=<existing publishable key, server-only>
SIMULATION_SERVICE_URL=<actual Render HTTPS backend URL>
SIMULATION_SERVICE_TOKEN=<same stable server token used by Render>
APP_URL=<actual stable production HTTPS origin>
DEVICE_TOKEN_ENCRYPTION_KEY=<retained server-only key when needed>
OPENAI_API_KEY=<authorized key if live AI is enabled>
OPENAI_MODEL=<configured model>
```

`GRIDIRON_COMPACT_API` is the deployment-specific transport flag; enable it only with the implemented compact-response/model-reference support. Never prefix provider keys or tokens with `NEXT_PUBLIC_`. Do not configure a Supabase service-role key as the app's user-scoped database client. Preserve the existing simulation token so saved model signatures remain valid across deployments.

The hosted workspace must remain cloud-only: a stale browser cookie must not switch it into an ephemeral SQLite ledger. Existing SQLite files remain preserved on their original server. Import an owned encrypted backup deliberately; do not reset the cloud database.

## Git and production checks

Connect the existing authorized GitHub repository and production branch. Keep `.env*`, `.vercel/`, local data and signing files out of Git. Save the previous production deployment ID before promoting a new release.

After a successful build, verify the returned stable HTTPS URL, `/api/health`, deep dependency health, anonymous account rejection, real Supabase login and owner isolation, exact ledger arithmetic, saved simulation reload, actual 10,000-game workflow and API failure states. Use isolated explicitly generated QA identities only. Physical Safari/Home Screen installation remains a separate user/device verification.

Set the Supabase Auth Site URL and permitted confirmation redirects to the exact production origin using authorized Auth configuration. Do not bypass its redirect allowlist. A functioning existing password session does not establish confirmation email delivery or a correct new-user redirect.

Official references checked: [Function limits](https://vercel.com/docs/functions/limitations), [function duration](https://vercel.com/docs/functions/configuring-functions/duration), and [project configuration](https://vercel.com/docs/project-configuration/vercel-json).
