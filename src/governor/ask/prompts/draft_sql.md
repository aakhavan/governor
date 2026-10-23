You write one DuckDB SQL query that answers a business question over a billing warehouse.

Tables, columns and metric definitions you may use (use these names without a schema prefix):

{context}

Plan for this question:

{plan}

Dates. The data was taken at {as_of}. Write every date as a literal (DATE 'YYYY-MM-DD'), resolved against that instant. Anchors computed from it:

{date_anchors}

Never call a function that reads the clock; such queries are rejected before they run.

Rules:
- One SELECT statement (WITH is fine). Name every column; no SELECT *.
- Give each output column a short snake_case alias.
- Follow the metric definitions above exactly when the plan names a metric.
- Order the rows when the question implies an order or a top-N.

Reply with one JSON object and nothing else:
{"sql": "<one SELECT statement>", "rationale": "<one sentence>"}

Question: {question}
