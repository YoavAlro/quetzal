# Emerix → Quetzal capability migration

Compared on 2026-08-02 against Emerix's `py/benchmarks/service_docs_qa` package. Quetzal should be
the reusable outsourced implementation; Emerix should supply only private suites and integration
glue.

## Capability matrix

| Capability | Emerix benchmark | Quetzal before | Migration result |
|---|---|---|---|
| Generic target/suite config | Monorepo constants | Yes | Keep Quetzal design |
| Claude CLI failure handling | Shared runner, reads stdout errors | Duplicated/basic | Ported shared runner |
| Codex isolation/current JSONL | Provider/effort, retries, modern events | Basic parser | Ported; also ephemeral |
| Cursor read-only enforcement | Ask mode + sandbox | Not enforced | Ported |
| OpenCode read-only telemetry | Plan/pure JSONL | Plain text, no tokens | Ported |
| Cached-input telemetry | Yes | No | Ported |
| API-equivalent pricing | Price book + override | No | Ported as packaged data |
| Duration reporting | Per case/suite/overall | Partial per-case only | Ported |
| Git provenance | Commit/branch/dirty | No | Ported |
| Retry only failures | Yes | No | Ported |
| Bounded suite size | 12 questions | Unlimited | Ported; configurable, 0 disables |
| Single-file export | Admin-console bundle | No | Ported as generic bundle |
| Early judge abort | Stops repeated bad configuration | Repeats all failures | Ported |
| Repo docs/skills/hooks health | No | Docs-maintenance hooks only | Added inventory + observed usage |
| Init and native docs hooks | No | Yes | Keep Quetzal design |
| All-in-one run→score→report | Separate commands | Yes | Keep Quetzal design |

## Intentional non-ports

- The raw API answerer and `emerix.agenticv3` judge stay in Emerix. They depend on private provider
  infrastructure, and the raw API answerer deliberately does not measure a coding-agent harness.
- Emerix service mappings, private questions, historical results, and admin-console upload wording
  stay in the monorepo. They are consumer data, not reusable library behavior.
- Quetzal does not claim exhaustive file or hook tracing. It records deterministic inventory and
  tool-input-visible usage, with explicit caveats in every report.

## Emerix cutover plan

1. Install and pin Quetzal in the Emerix Python workspace.
2. Point `quetzal.toml` at the monorepo and move each private suite JSON plus suite→root mapping into
   an Emerix-owned benchmark configuration directory.
3. Replace `service-docs-qa` commands in scripts/CI with `quetzal run`, `score`, `report`, and
   `export`; preserve existing result storage during a short dual-run period.
4. Run the same small suite through both implementations with the same harness/model/provider and
   compare answers, token/cache counts, cost, timing, and verdicts.
5. Switch the admin-console importer to Quetzal's `bundle.json` schema (or keep a thin Emerix
   translator), then remove duplicated portable modules from `service_docs_qa`.
6. Keep only private raw-API/provider adapters in Emerix as optional integration code if they remain
   useful; do not fork the core runner/report/storage again.

## Verification in this repository

- Ruff passes across package and tests.
- Ten unit tests cover backward compatibility, all four event parsers, input-only repo tracing,
  pricing, inventory pruning, and report aggregation.
- A live read-only Codex run (`migration-smoke-codex`) completed one case with cache/timing/cost
  telemetry and correctly observed one Markdown file out of three inventoried.
- Offline report and bundle export completed. A live Claude judge was not run because sending the
  benchmark payload to a second external provider was not approved in that execution environment.
