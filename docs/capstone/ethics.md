# Ethics and responsible use

governor puts language models into two jobs that matter to a business: building the tables its numbers come from, and answering questions with those numbers. This page says who could be harmed, what the system does about it, and what it does not do. The technical controls, each with the test that proves it, are in [`threat-model.md`](threat-model.md); this page is about consequences and judgment.

It is a portfolio project on a public dataset. Nothing here is a legal or compliance claim.

## Who is affected

| who | how they could be harmed |
|---|---|
| **Customers and sellers in the data** | their personal data (ids, zip prefixes, cities, review text) reaches a model provider, a log, a chat channel or someone not allowed to see it |
| **People who act on the numbers** | a wrong KPI looks official because it says "certified", and decisions (budgets, targets, performance reviews) follow from it |
| **The data team** | an agent changes production, or approvals become rubber stamps because the agent is usually right |
| **The organisation** | it cannot later explain where a number came from or who approved it |

## 1. Personal data

**Principle: models work on the shape of the data, never on the data.**

- Build-mode prompts carry table and column names, types, null rates, distinct counts and candidate keys. They carry no min, max or sample values, and personal-data columns appear as a name and a count only.
- dbt error messages can contain row values, so they are redacted before a repair prompt sees them (quoted literals blanked, `DETAIL` and `Failing row` lines dropped, long digit runs replaced).
- Questions in ask see KPI names and definitions, never values. The numbers in an answer are filled in by Python after the query runs.
- Personal data is protected by the database, not only by the model or the validator: analysts query views where PII columns are salted SHA-256 hashes, finance_admin sees a mask, and each role reads only its own schema through a read-only login. Person-level questions ("which customers in São Paulo…") are refused.
- Decision traces store the question as a hash and a length, not its text, unless debugging is switched on. Slack logs record the outcome and the KPI, never the question.

**What this does not solve.**

- **Hashing is pseudonymisation, not anonymisation.** Under GDPR (Recital 26) the analyst views still hold personal data: anyone with the salt, or enough outside information, can re-link them. They need the same care as the raw tables.
- **Metadata can be sensitive.** A column name like `hiv_status` or `union_member` tells a model provider something even with no values. On real data, names should be reviewed before profiling, or the profile sent to a model hosted in the EU or on-premises.
- **Questions go to a third party.** Certified-answer questions are sent through OpenRouter to the model provider. A user can type personal data into a question, and the certified path has no input screen for that (governor-ask's input guard catches some shapes, not all). A real deployment needs a data processing agreement with the provider, or a self-hosted model.
- **The dataset.** Olist published the data for research under CC BY-NC-SA 4.0, already anonymised (company names in reviews replaced). It is not committed here, and derived tables stay under its licence. That makes it suitable for a demo, not a stand-in for a company's own customers.

## 2. Trust in numbers

**Principle: "certified" has to mean something specific, and say what it does not mean.**

A certified KPI has passed the design checks, the blueprint rules L1–L9, a human design approval, a human review of the pull request, and a `certify` command run by a named person. Each answer cites the KPI id, its owner, the source of the definition, and who certified it when.

Certified does **not** mean correct. The known gap:

- **A well-typed but wrong mapping passes every code check.** If the design maps freight as item price, or a status filter keeps cancelled orders, the SQL is valid, the types fit, the template check passes, and the number is wrong. Only the reviewer at the design gate and the independent gold checks (`evaluation/build_gold/`) catch it. This is the main reason the design gate exists and is not automated away.
- **Definitions are choices.** GMV with or without freight, revenue gross or net of refunds: companies differ. The catalogue records the source and its tier for each definition (company glossary over accounting standards over platform docs over vendor glossaries), and a company's own glossary wins. A number is only as meaningful as the definition people agreed on.
- **Declining is a feature.** When the data cannot support a KPI (no session data for conversion rate, no unit costs for gross margin), governor says so and names the missing data instead of approximating. A plausible proxy answer would be easier to ship and worse for the people relying on it.

## 3. Human control

**Principle: the agent proposes; people decide anything that changes what others see.**

- Two gates: a person approves the design before any code is written, and a person reviews and merges the pull request before anything reaches production. `certify` is a terminal command that needs the admin login; it cannot be run from Slack.
- The build login can create tables only in a development schema. The deploy login can create only in `analytics`. The registry and the serving views are written by the admin login inside `certify`.
- The only memory a build learns from (`approved.yaml`) is written at the gate and reaches `main` only through the reviewed pull request, so an agent cannot quietly teach itself a wrong rule.
- A design with open findings cannot be approved, and only listed Slack users can press Approve.
- The evaluation harness approves designs automatically (recorded as `eval-harness` in each report). That bypass exists only inside the harness.

**Automation bias is the risk this cannot fully remove.** If the agent's designs are right most of the time, reviewers stop reading them. Mitigations in place: the design card shows counts, gaps and findings up front, and `design.md` explains each mapping. Not built yet: sampled re-review of approved designs, or seeding known-wrong designs to check that reviewers catch them.

## 4. Accountability and record keeping

- Every build emits events (who started it, what was proposed, who approved it, what was repaired, the cost) and every published build is a git commit with a pull-request description.
- The registry records `certified_by`, `certified_at` and the git commit for every KPI; serving views and answers can be traced back to a reviewed template and a named approver.
- Every governor-ask answer writes a redacted decision trace (plan, SQL attempts, validator codes, policy decisions, cost). The idea follows the EU AI Act's record-keeping article (Art. 12). governor is not a high-risk system under the Act, and this is not a compliance claim.

## 5. Scope and misuse

governor answers questions about aggregate business KPIs. It is not built to make or support decisions about individuals, and it refuses person-level questions. The same machinery could be pointed at employee or customer-level data to build surveillance metrics; the KPI catalogue is human-owned and reviewed for exactly that reason, and a deployment should keep person-level KPIs out of it.

## 6. Cost and footprint

Model calls are logged with their cost. The whole capstone evaluation cost about $0.46 in model calls; a build costs about $0.06 and a certified answer under a cent. Small models do the cheap structured jobs (picking a KPI, writing silver SQL); the larger model only plans the design.

## 7. What a real deployment would add

- A data processing agreement with the model provider, or an EU-hosted or self-hosted model.
- A review of column names before profiling sensitive sources.
- Per-person accounts instead of shared role tokens, so actions are attributable to individuals.
- Retention limits for traces, events and checkpoints, and a documented deletion path.
- Periodic re-review of certified KPIs, and recertification when a template or the source data changes.
