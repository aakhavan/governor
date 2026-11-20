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
