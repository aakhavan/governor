# governor

A modular data platform that builds and checks a company's medallion and KPI layer with agents, and answers business questions only from numbers it can stand behind. Product name to be decided; `governor` is the code name.

## Product

**Build mode**:
Designing and building a medallion and KPI layer from raw tables, under human approval.
_Avoid_: implement mode, greenfield mode

**Check mode**:
Assessing an existing platform against the layer blueprint and the KPI catalogue, without changing it.
_Avoid_: audit, scan, check-up agent

**Ask**:
The module that answers natural-language questions with governed SQL.
_Avoid_: chatbot, NL2SQL bot

## Standards

**Layer blueprint**:
The editable standard that defines the bronze, silver and gold layers, their mapping to project folders, the rules each layer must follow, and named exceptions.
_Avoid_: medallion template, layer rules file

**KPI**:
A measure a business of a given kind should track, defined once in the KPI catalogue independent of any one company.
_Avoid_: metric (when meaning the universal definition)

**KPI catalogue**:
The list of KPIs with their definitions, inputs, SQL templates, required data and prerequisites; extendable by a company.
_Avoid_: KPI list, metric catalogue

**Metric**:
How one company computes a KPI on its own data.
_Avoid_: KPI (when meaning the company's implementation)

**Certified**:
The state of a KPI whose metric passed the readiness checks and the review gate; only certified KPIs answer questions on the certified path.
_Avoid_: verified, trusted, approved (for KPIs)

**Buildable**:
A KPI whose required data exists in the warehouse; a KPI that is not buildable is declined with the missing data named.
_Avoid_: available, supported

## Approval and memory

**Design gate**:
The human approval of the layer plan, the KPI choice and the column mappings, before any code is written.

**Review gate**:
The human review and merge of the pull request that holds the built project.
_Avoid_: final approval

**Approved decisions**:
The reviewed record of column mappings, blueprint exceptions and corrections that later builds reuse.
_Avoid_: memory file, learned rules

**Certified path**:
Answering a KPI question by running the certified metric's reviewed SQL, with the model choosing only the KPI and its filters.
_Avoid_: semantic path, metric path

## Data

**Test bed**:
A platform governor is run against for development and evaluation; today the Olist dataset in Postgres.
_Avoid_: fixture (for the Postgres test bed), demo database

**Warehouse adapter**:
The plug that lets governor read, plan and run queries on one kind of warehouse.
_Avoid_: connector, driver

**Serving schema**:
The per-role view of the data that a role may query, with personal data hashed or masked.
_Avoid_: role schema, safe views
