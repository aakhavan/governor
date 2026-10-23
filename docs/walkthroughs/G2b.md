# G2b walkthrough: the golden set

*Gate review, 23 Oct 2026. Drafted by Claude from the step's output; read, edited and approved by Amir.*

**What it is.** 40 questions that a finance or ops analyst would ask, each with the answer we expect: correct SQL for 28 of them (24 answers, 2 aggregates, 2 masked), and for the other 12 the right behaviour instead of an answer (ask back, refuse, mask, or "not in this data"). This is the measuring stick for governor-ask. It is written before any agent prompt exists and then frozen with hashes (`FROZEN.sha256`), so I can't tune the agent to the test without it showing.

**Why 25 tune / 15 holdout.** I improve the agent only on the 25. The 15 are run once at the end; that number is the honest one.

**One question, traced.** m06: "How many invoices are overdue, and how much money is tied up in them?" "Overdue" is defined once, in `knowledge/metrics.yaml`: not void, not fully paid, outstanding more than 30 days at as_of. The gold SQL is that definition on `fct_invoices`: count of invoices and the unpaid amount (`amount_eur - paid_amount_eur`). The agent will have to find the same definition through retrieval, not invent its own.

**What the categories test.** Simple, joins, time and metrics test correctness. Ambiguous questions test that it asks back instead of guessing ("revenue last quarter": invoiced, collected or MRR?). Policy questions test the roles: an analyst may count contact emails but never see them; a finance admin sees names masked and the granted email in full.

**Limitations.** One small warehouse (4 marts), so this is a regression suite, not proof that it works on any schema. 15 holdout questions give a wide error bar. "Right now" means the September snapshot, because the data ends on 30 September. The gate also found that the build stamped as_of from the clock, so G3 now pins it in `fixture/AS_OF`.
