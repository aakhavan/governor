# LangGraph Studio

Studio is a developer view of the build and ask graphs. It is not the product UI. The product UI is the run console, which reads the same graphs through `/v1/console`.

Studio needs a LangSmith account. From the repo root:

```
uvx --from "langgraph-cli[inmem]" langgraph dev
```

`langgraph.json` names the two graphs and has no `env` key. The server reads `OPENROUTER_API_KEY` from the shell. When that key is unset, the graphs compile with the offline fake model.
