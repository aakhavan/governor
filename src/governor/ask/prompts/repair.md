A DuckDB SQL query written for a business question was rejected. Fix it.

Tables, columns and metric definitions you may use (use these names without a schema prefix):

{context}

Plan for this question:

{plan}

Dates. The data was taken at {as_of}. Write every date as a literal (DATE 'YYYY-MM-DD'), resolved against that instant. Anchors computed from it:

{date_anchors}

The rejected query:

{sql}

Why it was rejected (check codes from the validator, or the database's error):

{errors}

What the codes mean:
- PARSE_ERROR: not valid DuckDB SQL. MULTI_STATEMENT / NOT_SELECT: write exactly one SELECT.
- STAR: name the columns instead of * or a whole-row reference.
- COLUMN_UNKNOWN: use only columns listed above, on the right table.
- TABLE_FUNCTION: read only from the tables above or your own CTEs.
- VOLATILE_TIME: replace clock functions with date literals from the anchors.
- DRY_RUN_FAILED / EXEC_ERROR: the database could not plan or run it; read its message.

Keep the output columns of the rejected query unless the error is about them. Change only what is needed. Reply with one JSON object and nothing else:
{"sql": "<one SELECT statement>", "rationale": "<one sentence on what you changed>"}

Question: {question}
