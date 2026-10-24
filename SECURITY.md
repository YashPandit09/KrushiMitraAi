# Security policy

## Reporting a vulnerability

Please **do not open a public issue**. Report privately through GitHub's
[private vulnerability reporting](https://github.com/YashPandit09/KrushiMitraAi/security/advisories/new)
(Security tab -> "Report a vulnerability"). You should get an acknowledgement within a few days.

Only the latest `main` branch (and the `latest` container image) is supported.

## How the app is designed to be safe to run in public

- **No accounts, no personal data.** The app stores nothing about its visitors. All forecast data is read-only and
  generated offline by the pipeline.
- **No secrets in the repository.** The only optional secret (`DATA_GOV_IN_API_KEY`) is read from the environment
  on the server and is never sent to the browser. CI scans the full git history with gitleaks.
- **Bounded, allow-listed outbound calls.** The two live proxies (Open-Meteo weather, data.gov.in prices) only
  accept a known district slug and a known commodity key, call fixed HTTPS hosts with timeouts, do not follow
  redirects and cache responses - so traffic to the app cannot be amplified into traffic to third parties.
- **Rate limiting** on the live endpoints (per client IP, configurable).
- **Strict browser policy.** Content-Security-Policy (`default-src 'self'`, no third-party scripts, fonts or
  trackers), `X-Frame-Options: DENY`, `nosniff`, a strict referrer policy, a locked-down Permissions-Policy and HSTS
  when served over HTTPS.
- **Input validation** on every parameter (path patterns, enums, ranges); errors never expose stack traces.
- **Hardened container.** Slim base image, non-root user, no server banner; `docker-compose.yml` adds a read-only
  root filesystem, drops all Linux capabilities and sets `no-new-privileges`.
- **Supply chain.** Pinned Python dependencies and an npm lockfile, Dependabot updates, `pip-audit`, `npm audit`,
  CodeQL analysis, and an SBOM plus provenance attestation on every published image.
- **Safe model artefacts.** No pickled objects are loaded at runtime (the API serves JSON/CSV only), so tampered
  model files cannot execute code.

## Deployment notes

- Behind a reverse proxy, set `FORWARDED_ALLOW_IPS` to the proxy's address (or `*` only on platforms where the
  proxy is the sole way in, such as Render). Otherwise every visitor shares one rate-limit bucket.
- The rate limiter is in memory and per instance; for multiple replicas, put a limit at the proxy as well.
- Leave `CORS_ORIGINS` empty unless another site genuinely needs to call the API.
