# GRIDIRON AI PWA hosting on Railway

This deployment preserves the existing Next.js application and Python quantitative service. Supabase remains the persistent database and identity provider. It does not provision a new database, copy local user records automatically, or deploy the postponed native iPhone project.

Railway account authorization and an actual resource/billing review are required before publishing. The files in this directory are deployable configuration, not proof of a live deployment. A queued source upload is not a healthy production app.

## Runtime layout

| Service | Runtime | Network | Persistent records |
| --- | --- | --- | --- |
| `web` | Existing Next standalone server, non-root Node 22 | One generated HTTPS Railway domain, target port 8080 | Supabase Auth/PostgreSQL |
| `quant` | Existing FastAPI engine, one non-root Python worker | `http://quant.railway.internal:8080`; no public domain | Stateless computation; caller saves full inputs/results in Supabase |

Both services use Railway's runtime `PORT`. The Python entrypoint creates one IPv4/IPv6 socket so legacy IPv6-only private networks and current dual-stack networks work. The application binds its web server to `0.0.0.0`. Railway's encrypted private network carries app-to-engine HTTP; the engine additionally requires a stable server-only bearer token.

Hosted `GRIDIRON_CLOUD_ONLY=1` and `DATA_BACKEND=supabase` prevent an old browser's SQLite workspace cookie from selecting an ephemeral database. The original local SQLite workspace and Docker Compose deployment remain unchanged. Migrate its records only through the existing authenticated, reconciled encrypted-backup workflow; keep the original recovery copies.

## Source and tools

Use the pinned deployment SDK independently of app dependencies:

```sh
npm ci --prefix deployment/railway
node --test deployment/railway/test.mjs
python deployment/railway/test_runtime.py
node scripts/deploy-railway.mjs --check
```

The authoring file is `deployment/railway/railway.ts`, using `railway` 3.16.0. Railway CLI 5.71.0 was used to verify command help; install the matching official CLI through Railway's documented distribution. The optional `RAILWAY_BIN` variable can select its executable. Never print its authentication files or configure tokens in shell arguments.

Railway's current documentation deprecates `railway.json`/`railway.toml` Config as Code for new services and gives existing files a 2026-12-01 cutoff. This project uses the supported Infrastructure as Code authoring API. No deprecated root config is introduced.

## Authorized provisioning sequence

1. Connect the Railway account. Inspect the selected workspace, plan/credits, available CPU/RAM and billing limits. Reuse an existing authorized GRIDIRON project when appropriate. Obtain approval before adding paid resource use that has not already been authorized. Do not substitute an expiring development tunnel for permanent hosting.
2. Create or identify exactly two services named `web` and `quant` in the same project/environment. Keep any unrelated project services intact. Do not expose `quant` through a public domain. Use at least enough CPU/RAM to reproduce the observed real-engine timing; underpowered instances can exceed the existing 240-second upstream request bound. Local benchmark timing is not a guarantee of a particular hosted tier.
3. Set the required service secrets through the Railway connector or the secure stdin helper below. Copy the existing simulation token unchanged to both services; regenerating it invalidates saved fitted-artifact signatures and result attestations. Never put secrets into IaC, a Docker build argument, a public environment variable or a ZIP.
4. Link the current checkout to the explicitly selected project/environment using the CLI. Preview `railway config plan --file deployment/railway/railway.ts --environment <environment-id>`. The `gridiron-pwa` partial owns only the declared app services. Review the actual diff. Apply ordinary additions/settings only; do not pass a destructive-confirmation flag or delete existing resources. Missing preserved secrets must be configured first.
5. Generate one HTTPS domain for `web` using `railway domain --project <project-id> --environment <environment-id> --service <web-service-id> --port 8080 --json`. Keep its returned literal URL. The runtime derives `APP_URL` from `RAILWAY_PUBLIC_DOMAIN` if no explicit origin is set, and rejects placeholders/insecure remote origins. Prefer explicitly setting `APP_URL` to that same returned HTTPS origin.
6. Configure Supabase Auth's Site URL and allowed redirects for the returned origin. Confirm email delivery and the real email-confirmation workflow. A successful password-session test does not prove email delivery or redirect configuration.
7. Upload the existing source to both services without requiring a GitHub repository. Poll the exact deployment IDs until healthy, inspect logs, and perform the live workflow below. Do not report success merely because build/upload commands were accepted.

The source-helper selectors are non-secret exact UUIDs:

```text
GRIDIRON_RAILWAY_PROJECT_ID
GRIDIRON_RAILWAY_ENVIRONMENT_ID
GRIDIRON_RAILWAY_WEB_SERVICE_ID
GRIDIRON_RAILWAY_QUANT_SERVICE_ID
```

CLI authorization uses **one** of `RAILWAY_TOKEN` (project scoped) or `RAILWAY_API_TOKEN` (account/workspace scoped), supplied through a trusted runtime secret channel. The helper refuses missing/ambiguous authentication or missing exact service selectors. It never starts an implicit browser login, creates a project, or picks an arbitrary account.

For setting service values, `node scripts/deploy-railway.mjs --configure` accepts a single JSON object on stdin with `web`/`quant` objects and permitted variable names. Use a trusted tool or secret manager to supply this object; do not paste actual values into command history. It calls Railway's single-variable stdin interface with `--skip-deploys`, captures raw output, and prints only the count of configured keys. `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` and the same stable `SIMULATION_SERVICE_TOKEN` are required. Optional OpenAI, licensed odds and device-encryption keys remain server-only.

After resource/billing permission has actually been established, set `GRIDIRON_RAILWAY_BILLING_APPROVED=1` in the operator environment and run:

```sh
node scripts/deploy-railway.mjs --upload
```

This stages a source-only temporary tree, excludes runtime financial records/secrets/caches/signing files, uploads it to the explicit existing `quant` and `web` services, then removes only that helper-owned temporary copy. The original project/data stay unchanged. Its output says **queued**, not deployed; use the connected provider to observe terminal status.

## Environment contract

| Variable | Service | Purpose |
| --- | --- | --- |
| `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` | web | Existing Supabase project; no service-role secret |
| `SIMULATION_SERVICE_TOKEN` | both | Identical stable server secret, at least 32 characters |
| `SIMULATION_SERVICE_URL` | web | Private `quant.railway.internal` HTTP endpoint |
| `APP_URL` | web | Exact HTTPS web origin; derives from Railway's generated domain when absent |
| `GRIDIRON_CLOUD_ONLY=1`, `DATA_BACKEND=supabase` | web | Durable cloud workspace with no ephemeral SQLite selection |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | web, optional | Real AI streaming/tool calls; absence remains visible |
| `ODDS_API_KEY` | web, optional | Authorized sportsbook provider entitlement; not a DK Predictions direct-feed entitlement |

IaC preserves required secret values already stored on Railway. Optional provider keys are intentionally not hardcoded or invented. No persistent Railway volume is required for cloud-only financial/research records. Add no disposable database as a replacement for Supabase.

## Live acceptance checks

Verify the returned HTTPS URL, deployment terminal status and logs. `/api/health` is a non-sensitive liveness endpoint; `/api/health?check=dependencies` performs bounded Supabase/private-engine readiness checks. Neither response proves a model is calibrated.

Use a clearly isolated QA account to test actual sign-in, owner isolation, NFL source import, fitted real-input 10,000-game simulation, saved-result reopening, supported sourced injury scenarios and explicitly identified manual binary contracts. Verify deposit/withdrawal/settlement arithmetic, reload/new-session continuity and real AI database retrieval if an OpenAI key is configured. Remove only explicitly disposable test fixtures after verification. Never reset real accounts or a production database.

Test manifest/icons, HTTPS service-worker scope, no private API caching, offline shell, iPhone layouts and Safari Add to Home Screen behavior. A browser's iPhone viewport is not a physical-device installation test. No Xcode or IPA work is part of this PWA release.

## Documentation sources checked

- https://docs.railway.com/infrastructure-as-code
- https://docs.railway.com/infrastructure-as-code/reference
- https://docs.railway.com/cli/up
- https://docs.railway.com/cli/login
- https://docs.railway.com/cli/domain
- https://docs.railway.com/networking/private-networking

Actual deployment and production verification results belong in the current delivery report, including any authorization or billing blocker. Do not convert these instructions into a claim that hosting is already live.

## Executed local deployment verification

Both Railway-specific Docker images built successfully. The web image was rebuilt with nested deployment-tool dependencies excluded, confirming a fresh cloud build does not need the isolated IaC SDK during Next compilation. Five Node deployment checks and two Python runtime checks passed.

`deployment/railway/container-verification.json` records actual local Docker acceptance: non-root Node startup; real remote Supabase dependency reachability; private bridge-network Python readiness; IPv4 and IPv6 health; anonymous financial access rejected with 401; hosted SQLite selection rejected with 409; and no `.env` or user SQLite file in the runtime image. A separate staged-source scan examined 197 source files and found none of the configured publishable-key/token/encryption-key values.

The container check creates only uniquely named local containers/network and removes those owned test resources afterward. It makes no financial writes or user-account changes. To repeat after building the tagged images with the appropriate trusted CA mounts for your environment:

```sh
node deployment/railway/verify-containers.mjs
```

The managed authoring environment injects both uppercase and lowercase proxy settings into Docker. This local check sets both `NO_PROXY` and `no_proxy` for its private `quant` bridge alias; otherwise an injected lowercase proxy rule can wrongly route private health traffic through the outbound proxy. This is local-test network configuration, not a claim that Railway injects those proxy settings.

No Railway account was authorized during these checks. Remote IaC planning/application, paid resource provisioning, service upload, generated HTTPS domain, hosted logs and production Safari installation therefore remain **not run**. The supplied configuration and passing local images cannot substitute for that external authorization.
