You write one DuckDB SQL query that answers a business question over a billing warehouse.

The warehouse has these tables. Use only these tables and columns, without a schema prefix.

{schema}

The data was taken at {as_of}. Resolve relative dates ("last month", "this year", "overdue") against that instant, written as date literals. Do not use now(), current_date or current_timestamp.

Reply with one JSON object and nothing else:
- to answer: {"action": "sql", "sql": "<one SELECT statement>"}
- if the question cannot be answered with one query over these tables: {"action": "refuse", "reason": "<one sentence>"}

Question: {question}
