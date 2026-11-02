# governor writes only to its own branch and a dev schema, behind two human gates

Build mode means governor writes code and creates tables, which the read-only design never did. It writes dbt files only to its own git branch and builds only into `dev_governor` through a role that can create tables nowhere else. A person approves the design before code is written and reviews and merges the pull request; production tables are built only after that merge. ask keeps reading production data through its read-only role.

## Considered Options

- One gate at the end: rejected, a wrong design would waste a full build and the review would be too large.
- A gate on every model: rejected, too slow for a person to keep up with.
