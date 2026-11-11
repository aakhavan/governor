# Threat model: what the models read, and what stops them

Scope: the two places governor hands text to a language model. **Build mode** proposes a silver layer and KPI
mapping, writes intermediate SQL and column docs. **Ask** answers a business question over the served warehouse.
OWASP agentic risk ids (ASI01 to ASI10) are used for the table below.

## What a model reads

**Build mode** reads identifiers, counts and human-owned files only:

- the profile as table and column names, inferred types, null rates, distinct counts, candidate keys and row
  counts; no min, no max, and PII columns as name and counts only (`design.profile_for_prompt`);
- human-owned files: the blueprint rules, the KPI catalogue (definitions, not templates), `approved.yaml`;
- the design itself (model and column names, descriptions, expressions written by the plan model);
- on a silver repair, its own SQL and the dbt error after `redact_error`: `DETAIL`, `HINT`, `CONTEXT`,
  `Failing row` and `Key (` lines dropped, single-quoted literals as `'…'`, double-quoted spans kept only when they
  name a model, column, raw table, raw column or schema of the design, and 7 or more digits as `#`.

**Ask** reads the semantic cards and the question to plan and write SQL. The SQL is validated against the role's
policy before it runs as a read-only reader login; PII is refused or masked by role. Numbers in the reply come from
the result rows, not from the model (`tests/ask/test_graph.py::test_answer_numbers_come_from_result`).

Untrusted text that can reach a model: raw column and table names (they come from the source system), the free
text of `approved.yaml` reasons, and error messages. The propose and describe prompts carry no data values. In a
repair prompt, quoted literals, the five dropped line prefixes and runs of 7 or more digits are removed; an unquoted
value on a kept line is unchanged (`tests/build/test_threats.py`: `test_repair_prompt_redacts_data_values`,
`test_redaction_keeps_known_identifiers`, `test_redaction_drops_detail_lines_and_long_numbers`).

## Risks, controls and evidence

| OWASP agentic risk | Governor's control | Evidence |
|---|---|---|
| ASI01 Goal hijack | Prompts carry identifiers and counts, never values; an instruction-shaped column name stays a JSON name inside the profile block; an approved reason stays inside its block; whatever the model proposes is checked by code (`design.validate`) before the gate; repair errors are redacted | `tests/build/test_threats.py`: `test_propose_prompt_has_no_data_values`, `test_describe_prompt_has_no_data_values`, `test_instruction_named_column_stays_in_the_profile_block`, `test_approved_decision_text_stays_in_its_block`, `test_hijacked_proposals_get_findings`, `test_repair_prompt_redacts_data_values`; ask: `evaluation/redteam/attacks.yaml`, `tests/eval/test_redteam.py` |
| ASI02 Tool misuse | Code owns the edges: staging SQL is generated from the design, model SQL must be one SELECT with only declared `ref()`s and no DDL or DML (`check_sql`); the build workspace uses schema `dev_governor` and a build password with no default; gold is written from catalogue templates and checked against L1 to L9 | `tests/build/test_silver.py`: `test_staging_sql_is_code`, `test_check_sql_refuses`, `test_staging_may_read_only_its_own_raw_table`; `tests/build/test_workspace.py`: `test_layout`, `test_no_secret_and_password_has_no_default`; `tests/build/test_gold.py::test_each_rule_fires_on_a_crafted_bad_project`; `tests/build/test_threats.py::test_pii_in_gold_is_an_l7_finding` |
| ASI03 Privilege abuse | Separate ask, build and deploy logins; the build password has no default; deploy creates only in `analytics`; ask runs as a read-only reader role taken from the token (API), the server config (MCP, Slack), never from the request | `tests/build/test_workspace.py::test_no_secret_and_password_has_no_default`, `tests/build/test_publish.py::test_live_deploy_role_creates_only_in_analytics`, `tests/api/test_api.py::test_role_comes_from_token`, `tests/api/test_api.py::test_role_in_body_rejected`, `tests/mcp/test_mcp_server.py::test_role_comes_from_the_environment`, `tests/integrations/test_slack_ask.py::test_ask_role_comes_from_config_only`, `tests/testbed/test_serving.py::test_reader_roles_isolated` |
| ASI06 Memory poisoning | The only memory a build reads is `approved.yaml`; the gate appends decisions to the target project and they reach `main` only through the reviewed pull request; the file is schema-checked on load | `tests/build/test_design.py::test_record_decisions_appends_and_supersedes`, `tests/build/test_publish.py::test_publish_inits_branches_commits_and_writes_pr`, `tests/integrations/test_slack_next.py::test_pr_button_requires_approver`, `tests/core/test_catalogue.py::test_approved_decision_validation` |
| ASI09 Human-agent trust | Findings are shown on the design card and a report with findings cannot be approved; staging keys are checked against the profile's candidate keys before the gate (batch2c section 19); only an approver can press Approve | `tests/build/test_design.py::test_report_with_findings_is_not_approvable`, `tests/build/test_graph.py::test_design_repair_fixes_key_before_the_gate`, `tests/integrations/test_slack.py::test_design_card_has_counts_gaps_and_buttons`, `tests/integrations/test_slack.py::test_non_approver_cannot_approve` |

## Open findings and limits

- All five hijack shapes in `test_hijacked_proposals_get_findings` get a finding from `design.validate` today
  (unknown source table, unknown raw column, unknown KPI, PII passed on untagged, boolean over an undeclared
  column). No shape is marked xfail, so there is no open validation finding from this step.
- A well-typed but wrong mapping (a real column of the right type, the wrong meaning: freight mapped as item price,
  a status filter that keeps cancelled orders) passes every code check, L8 included: L8 catches gold SQL that
  differs from a fresh render of the approved mapping, so a wrong mapping that is the approved design passes it.
  Only the reviewer at the design gate and the gold value evaluation in `evaluation/build_gold` can catch it.
- Redaction is by shape, not by meaning: a value written unquoted inside an error line that is not dropped would
  pass through. Postgres quotes the values it reports, and the known forms are covered by
  `test_redaction_drops_detail_lines_and_long_numbers`.
- Redaction also blanks single-quoted text in code-made messages (`ref('stg_x')` shows as `ref('…')`); the model
  still has its own SQL and the model block, so the repair keeps its context.
- The stored failure and the escalation record keep the raw error for the operator; Slack scrubs what it shows
  (`tests/integrations/test_slack_cleanup.py::test_escalation_reason_names_failing_tests`,
  `tests/integrations/test_slack_ask.py::test_ask_error_is_scrubbed_and_ephemeral`).
- Ask: the answer runs over a role-filtered result. A value the role may see is data that can meet the answer
  model; it is not a PII leak, and no test here bounds what the answer prompt contains.
