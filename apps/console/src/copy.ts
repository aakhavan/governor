export const copy = {
  appName: "Governor",
  tagline: "Watch a build or a question move through the graph.",
  skip: "Skip to content",
  navLabel: "Console",
  navRuns: "Runs",
  navBuild: "Build graph",
  navAsk: "Ask graph",
  themeToLight: "Light theme",
  themeToDark: "Dark theme",
  runsTitle: "Runs",
  runsLead: "Live logs and shipped demos, newest first.",
  refresh: "Refresh",
  loading: "Loading…",
  noRuns: "No runs yet.",
  apiDown: "The console API is not reachable.",
  runMissing: "This run is not in the log.",
  colRun: "Run",
  colGraph: "Graph",
  colStarted: "Started",
  colStatus: "Status",
  colElapsed: "Elapsed",
  colCost: "Cost",
  demo: "demo",
  graphBuild: "Build",
  graphAsk: "Ask",
  unknownGraph: "Unknown graph.",
  buildLead: "Every step a build can take.",
  askLead: "Every step a question can take.",
  followLive: "Follow live",
  showList: "Show steps as a list",
  showCanvas: "Show the canvas",
  leftToRight: "Left to right",
  topToBottom: "Top to bottom",
  live: "Live",
  replay: "Replay",
  watchLive: "Watch live",
  restart: "Restart",
  speed1: "1×",
  speed4: "4×",
  speed16: "16×",
  reconnecting: "Reconnecting…",
  tabSteps: "Steps",
  tabNode: "Node",
  noEvents: "Events will show up here as the run moves.",
  selectNode: "Select a step to read its summary.",
  attempts: "Attempts",
  duration: "Duration",
  summary: "Summary",
  errorCode: "Error code",
  description: "What it does",
  state: "State",
  canvasError: "The canvas could not be drawn.",
  nodePending: "Not started",
  nodeRunning: "Working…",
  nodeSkipped: "Skipped",
  nodePlanned: "Coming soon",
  nodePausedApproval: "Waiting for approval",
  nodePausedAnswer: "Waiting for an answer",
  nodeFailed: "Failed",
  stateDone: "Done",
  statePaused: "Paused",
  emdash: "—",
  costUnknown: "—",
  llmCalls: "LLM calls",
  tokens: "Tokens",
  cost: "Cost",
  elapsed: "Elapsed",
  unitMs: "ms",
  unitSeconds: "s",
  unitMinutes: "m",
  utc: "UTC",
  none: "None",
  groups: {
    design: "Design",
    silver: "Silver",
    gold: "Gold",
    understand: "Understand",
    sql: "SQL",
    answer: "Answer",
  },
  statuses: {
    running: "Running",
    paused: "Paused",
    finished: "Finished",
    failed: "Failed",
    built: "Built",
    escalated: "Escalated",
    design_invalid: "Design invalid",
    up_to_date: "Up to date",
    answered: "Answered",
    refused: "Refused",
    awaiting_approval: "Awaiting approval",
    awaiting_clarification: "Awaiting an answer",
    pass: "Pass",
    gap: "Gap",
    declined: "Declined",
  },
  events: {
    run_started: "Run started",
    node_started: "Started",
    node_finished: "Finished",
    node_failed: "Failed",
    run_paused: "Paused",
    run_resumed: "Resumed",
    run_finished: "Run finished",
  },
  views: {
    tabSummary: "Summary",
    tabLineage: "Lineage",
    tabFunnel: "Build funnel",
    tabKpi: "KPI evidence",
    tabGuard: "Guard path",
    results: "Results",
    summaryCaption:
      "These tiles show the time, tables, models, tests, KPIs, gaps, model calls and cost for this build. They tell you whether the run produced a warehouse or stopped short.",
    summaryEmpty: "Wait until this build records a step, or open a finished build run.",
    lineageCaption:
      "Each column is a layer, from raw tables through silver and gold to KPIs, and a gap KPI is drawn with a dashed border. Click any node to highlight what feeds it and what it feeds.",
    lineageEmpty: "Finish a build that writes a manifest to see the path from raw tables to KPIs.",
    funnelCaption:
      "The bars count how many KPIs were requested, computable, proposed, validated and built. The lower chart shows what the guard rails stopped.",
    funnelEmpty: "Finish a build to see how many KPIs made it through each stage.",
    funnelStopped: "What the guard rails stopped",
    funnelClear: "Nothing was stopped on this build.",
    kpiCaption:
      "The donut counts KPIs that were built, left as gaps, or declined. Each card names the models that feed that KPI and the tests that passed on the build.",
    kpiEmpty: "Finish a build to see which KPIs were built, which are gaps, and which were declined.",
    guardCaption:
      "Each step is a check the question had to pass, with the refusal code and any repair that ran between checks. Every query passes these checks before it touches the warehouse.",
    guardEmpty: "Ask a question to see which checks passed, which refused it, and whether a repair ran.",
    tables: "Tables profiled",
    models: "Models",
    tests: "Tests passed",
    kpisBuilt: "KPIs built",
    gaps: "Gaps",
    requested: "Requested",
    computable: "Computable",
    proposed: "Proposed",
    validated: "Validated",
    built: "Built",
    layerRaw: "Raw",
    layerSilver: "Silver",
    layerGold: "Gold",
    layerKpi: "KPI",
    checkGuard: "Guard",
    checkValidate: "Validate",
    checkDryRun: "Dry run",
    checkExecute: "Execute",
    checkAnswer: "Answer",
    notReached: "Not reached",
    repairStep: "Repair",
    noModels: "No model feeds this KPI.",
  },
} as const;

export function attemptBadge(attempts: number): string {
  return `×${attempts}`;
}

export function nodeAria(label: string, status: string): string {
  return status ? `${label}, ${status}` : label;
}

export function statusText(status: string | null | undefined): string {
  if (!status) return copy.emdash;
  const known = copy.statuses[status as keyof typeof copy.statuses];
  return known ?? status.replaceAll("_", " ");
}

export function eventText(type: string | undefined): string {
  if (!type) return copy.emdash;
  const known = copy.events[type as keyof typeof copy.events];
  return known ?? type.replaceAll("_", " ");
}

export function graphText(graph: string | null | undefined): string {
  if (graph === "build") return copy.graphBuild;
  if (graph === "ask") return copy.graphAsk;
  return copy.emdash;
}

export function groupText(group: string): string {
  const known = copy.groups[group as keyof typeof copy.groups];
  return known ?? group;
}

export function runLabel(state: string, status: string | null): string {
  if (state === "failed") return statusText("failed");
  if (status) return statusText(status);
  return statusText(state);
}
