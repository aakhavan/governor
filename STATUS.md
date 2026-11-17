# STATUS: governor

Updated 17 Nov 2026 18:29. Run `20261117-175306`.

| step | title | tier | gate | state | loops | reason | implementer | verdicts | updated |
|---|---|---|---|---|---|---|---|---|---|
| F1 | Safety rails (database connection timeout, active workspace in the bot) | design | - | done | 0/2 |  | claude-tc-opus | claude-tc-fable: pass | 2026-11-17T16:58:26 |
| F2 | Profile fingerprint and drift | design | - | done | 0/2 |  | claude-tc-opus | claude-tc-fable: pass | 2026-11-17T17:23:23 |
| F3 | Up-to-date runs and drift-aware design | design | - | done | 0/2 |  | claude-tc-opus | claude-tc-fable: pass | 2026-11-17T17:56:23 |
| F4 | Publish against a stale main, nothing to publish | design | - | done | 0/2 |  | claude-tc-opus | claude-tc-fable: pass | 2026-11-17T18:10:14 |
| F5 | Tenants (registry, per-tenant build, CLI --tenant) | design | - | passed | 0/2 |  | claude-tc-opus | claude-tc-fable: pass | 2026-11-17T18:29:03 |
| F6 | One Slack bot for several tenants | design | yes | pending | 0/2 |  | - | - | - |

Cost so far (reported + notional): $143.89 of $90.00 run budget; 159 agent call(s).

Next: F5 is passed: `factory resume`.
