# Gold KPIs are generated from catalogue templates; the model maps, it does not write

Agents that write transformation SQL freely are unreliable (ELT-Bench: correct transformation models in 3.9% of pipelines; best Spider 2.0-DBT score 65.6%). KPI definitions are close to universal, so each KPI in the catalogue carries a SQL template with named inputs; in build mode the model maps raw columns to those inputs and code checks the mapping by profiling. Silver models, which differ too much between sources to template, are written by the agent under tests and human review.

## Considered Options

- Free SQL for every layer, checked only by tests: rejected, too unreliable for numbers a business acts on.
- Templates for silver as well: rejected, source cleaning varies too much between companies.
