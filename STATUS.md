# STATUS: governor

Updated 17 Nov 2026 17:56. Run `20261117-175306`.

| step | title | tier | gate | state | loops | reason | implementer | verdicts | updated |
|---|---|---|---|---|---|---|---|---|---|
| F1 | Safety rails (database connection timeout, active workspace in the bot) | design | - | done | 0/2 |  | claude-tc-opus | claude-tc-fable: pass | 2026-11-17T16:58:26 |
| F2 | Profile fingerprint and drift | design | - | done | 0/2 |  | claude-tc-opus | claude-tc-fable: pass | 2026-11-17T17:23:23 |
| F3 | Up-to-date runs and drift-aware design | design | - | passed | 0/2 |  | claude-tc-opus | claude-tc-fable: pass | 2026-11-17T17:56:22 |
| F4 | Publish against a stale main, nothing to publish | design | - | pending | 0/2 |  | - | - | - |
| F5 | Tenants (registry, per-tenant build, CLI --tenant) | design | - | pending | 0/2 |  | - | - | - |
| F6 | One Slack bot for several tenants | design | yes | pending | 0/2 |  | - | - | - |

Cost so far (reported + notional): $135.83 of $90.00 run budget; 155 agent call(s).

Next: F3 is passed: `factory resume`.
