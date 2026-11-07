# Online handoff — no public deployment performed

One persistent Linux VM runs CaddyTLS -> one FastAPI worker -> privatePostgreSQL.
The existing application/model/engine remain authentic. Browser users install
nothing after an authorized public HTTPS deployment. There is currently **no live
external URL**. localhost staging is not online publication.

## Local verified staging (Docker Desktop / Compose2.24.4+)

From the exported source root, set only non-secret values:

```sh
export MAHJONG_PUBLIC_HOST=localhost
export MAHJONG_HTTP_PORT=18080
export MAHJONG_HTTPS_PORT=18443
docker compose -f compose.yaml -f deploy/compose.https.yaml -f deploy/compose.local-tls.yaml build web db
docker compose -f compose.yaml -f deploy/compose.https.yaml -f deploy/compose.local-tls.yaml --profile tools run --rm --no-deps bootstrap
docker compose -f compose.yaml -f deploy/compose.https.yaml -f deploy/compose.local-tls.yaml up -d --wait
```

The proxy binds127.0.0.1. It has a private local CA. Use only its **public root
certificate** for an isolated test client's `--ca`; do not copy private keys,
install global CA trust, use insecureTLS flags or bypass browser warnings.
The default Caddyfile uses publicACME; the local override alone uses internalTLS.
Backend and DB have no host port. Healthchecks send the configuredHost.
Front addresses reserve proxy172.30.43.2 and web172.30.43.3; if the subnet overlaps
an existing network, choose a new private subnet and update the exact trusted IP
together. Do not use wildcard/CIDR trust or trust forwarded public-client headers.

## After separate publication authorization

1. Owner supplies/approves a cloud account, persistent VM, charges/budget, domain
   and permission to publish this model-backed service. No credentials go in Git.
2. Use a maintained Linux VM with Docker/Compose. Proposed starting budget:
   >=2GiBRAM,2vCPU,20+GiBSSD; this is headroom guidance, not a measured public
   capacity guarantee. ARM64 staging tested; other server architectures need
   native build/acceptance. Do not autoscale/sleep this in-memory-game application.
3. Transfer only the checksum-verified exported runtime/source package, not the
   audit archive, raw data, devDB or developer.env. Generate a new stable secret
   set via bootstrap; retain it privately with the PG/Caddy volumes.
4. Set MAHJONG_PUBLIC_HOST to the approvedDNS hostname. After authorization only,
   set MAHJONG_BIND_ADDRESS=0.0.0.0, MAHJONG_HTTP_PORT=80 and MAHJONG_HTTPS_PORT=443, and configure
   the domain/firewall appropriately. Keep backend8000/PG5432 inaccessible.
5. Use compose.yaml + deploy/compose.https.yaml, **without localTLS override**.
   Caddy obtains publicACME certificates; persist its volumes. Singleinstance,
   one worker; no development reloader. Keep OS/images patched/backups private.
6. Run smoke_online against the actualHTTPS origin using normal systemCA trust;
   verify externaldesktop/mobile access, DNS/TLS, cookies, CSRF, host/proxy security,
   fullround/v3/history and restart before calling it ONLINEPASS.

App restart loses unfinishedgames; history survives with the same secret/cookie.
Current limits/ownership/legalactions/CSP remain unchanged. Configure allowedhosts
explicitly; productionSecurecookies are mandatory. Forwarded headers are trusted
only from Caddy's reservedIP. Caddy replaces client-suppliedforwarded values.

## Hosting choice / budget (checked6November2026)

Prefer an always-running VM for this project: one authoritative process and one
local persistentPG avoid distributed-state refactoring. The template is provider
neutral. DigitalOcean's official Basic table lists2GiB/2vCPU/60GiB at$18/month;
tax/domain/backups/overages may add cost. This is a current price example, not a
resource purchase, quote guarantee or endorsement of untested capacity:
https://www.digitalocean.com/pricing/droplets

Renderfree was considered and rejected as the default: it sleeps after15minutes
idle, its filesystem is ephemeral, and freePG expires after30days. That does not
meet predictable game/history availability. PaidPaaS remains possible but needs
explicit instance/no-sleep/resource/DB budget verification:
https://render.com/docs/free

Official proxy/merge references:
https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#defaults
https://docs.docker.com/reference/compose-file/merge/#reset-value

## Operations / diagnostics

Use `docker compose ... ps` and ownedservice logs locally. Do not share.env,
secretfiles, signing keys, cookies, CSRF tokens or privateSQL. Never run down-v
as a routine restart. Stop preservesvolumes. Back up only with authorized private
procedures; no production-data transfer is part of Phase4.3.
For wronghost/TLS/502, check DNS/allowedhosts, reservedproxyIP, health and whether
the local-only test override was accidentally deployed. Resource exhaustion is a
failure, not a fake success page. No free-tier uptime/publicURL is promised.
