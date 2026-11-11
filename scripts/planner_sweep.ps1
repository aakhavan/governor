# Planner sweep on the frozen build evaluation (docs/capstone/batch2d.md section 26). Human run: real models, real Olist.
# Needs: the dev test bed up with the real Olist data in raw, and the usual build environment (OPENROUTER_API_KEY,
# GOVERNOR_BUILD_PASSWORD). Writes only under evaluation/reports/sweep/ and evaluation/sweep_report.md.
#   .\scripts\planner_sweep.ps1            # 5 runs per planner
#   .\scripts\planner_sweep.ps1 -Runs 3
param(
    [int]$Runs = 5,
    [string[]]$Planners = @("openai/gpt-6.1-sol", "anthropic/claude-sonnet-5.5", "openai/gpt-5-mini"),
    [string]$WriteModel = "openai/gpt-5-mini",
    [double]$MaxCostUsd = 2.0
)
$ErrorActionPreference = "Continue"
$out = "evaluation/reports/sweep"
New-Item -ItemType Directory -Force -Path $out | Out-Null
foreach ($p in $Planners) {
    $tag = ($p -replace "[^A-Za-z0-9]", "_")
    Write-Host "== planner $p, $Runs runs"
    uv run python -m governor.eval.build_eval --system agent --runs $Runs --gold evaluation/build_gold/olist_gold.yaml `
        --out "$out/build_agent_$tag.json" --plan-model $p --write-model $WriteModel --max-cost-usd $MaxCostUsd
    if ($LASTEXITCODE -ne 0) { Write-Host "   planner $p failed (exit $LASTEXITCODE); continuing" }
}
uv run python scripts/sweep_csv.py $out
uv run python -m governor.eval.capstone_report --reports $out --out evaluation/sweep_report.md
