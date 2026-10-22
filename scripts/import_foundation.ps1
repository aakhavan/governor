<#
.SYNOPSIS
  Copies the Sprint 4 foundation into this repo (HUMAN step, after the Sprint 4 submission).
  Copies only the listed code/config files; never .env, data, artifacts or dbt target folders.
  Writes PROVENANCE.md (source path, sha256, sprint git commit). Refuses to overwrite unless -Force.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\import_foundation.ps1
#>
param(
  [string]$Source = (Join-Path $HOME 'Turing College\sprint-04-incident-triage'),
  [switch]$Force
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path $Source)) { throw "Sprint 4 folder not found: $Source (pass -Source <path>)" }

# Sprint 4 project root: the folder that holds src\triage (it may be $Source or $Source\project)
$S4 = $Source
if (-not (Test-Path (Join-Path $S4 'src\triage'))) {
  $cand = Get-ChildItem $Source -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'src\triage') } | Select-Object -First 1
  if ($cand) { $S4 = $cand.FullName } else { throw "src\triage not found under $Source" }
}

$files = @(
  @('src\triage\llm.py',        'src\governor\core\llm.py'),
  @('src\triage\security.py',   'src\governor\core\security.py'),
  @('src\triage\trace.py',      'src\governor\core\trace.py'),
  @('src\triage\harvest.py',    'src\governor\core\harvest.py'),
  @('src\triage\lineage.py',    'src\governor\core\lineage.py'),
  @('src\triage\retrieval.py',  'src\governor\core\retrieval.py'),
  @('knowledge\owners.yaml',    'knowledge\owners.yaml'),
  @('knowledge\policy.yaml',    'knowledge\policy.yaml')
)
$testPatterns = @('test_llm*.py','test_security*.py','test_trace*.py','test_harvest*.py','test_lineage*.py','test_retrieval*.py')

$rows = New-Object System.Collections.Generic.List[string]
$missing = New-Object System.Collections.Generic.List[string]

function Copy-One([string]$from, [string]$to) {
  $src = Join-Path $S4 $from; $dst = Join-Path $Repo $to
  if (-not (Test-Path $src)) { $missing.Add($from); return }
  if ((Test-Path $dst) -and -not $Force) { throw "exists: $to (use -Force to overwrite)" }
  New-Item -ItemType Directory -Force (Split-Path -Parent $dst) | Out-Null
  Copy-Item $src $dst -Force
  $h = (Get-FileHash $dst -Algorithm SHA256).Hash.Substring(0,12).ToLower()
  $rows.Add("| ``$($to -replace '\\','/')`` | ``$($from -replace '\\','/')`` | $h | unchanged |")
}

foreach ($f in $files) { Copy-One $f[0] $f[1] }

# tests for the copied modules
$testDir = Join-Path $S4 'tests'
if (Test-Path $testDir) {
  foreach ($p in $testPatterns) {
    Get-ChildItem $testDir -Filter $p -File -ErrorAction SilentlyContinue | ForEach-Object {
      Copy-One ("tests\" + $_.Name) ("tests\core\" + $_.Name)
    }
  }
}

# fixture folder, without generated output
$fx = Join-Path $S4 'fixture'
if (Test-Path $fx) {
  $dstFx = Join-Path $Repo 'fixture'
  if ((Test-Path $dstFx) -and -not $Force) { throw "exists: fixture (use -Force to overwrite)" }
  robocopy $fx $dstFx /E /NFL /NDL /NJH /NJS /NP /XD target logs dbt_packages __pycache__ .venv /XF *.duckdb *.duckdb.wal .user.yml *.pyc .env .env.* | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
  $n = (Get-ChildItem $dstFx -Recurse -File).Count
  $rows.Add("| ``fixture/`` ($n files) | ``fixture/`` | - | unchanged; target/, logs/, *.duckdb excluded |")
} else { $missing.Add('fixture\') }

$commit = ''
try { $commit = (git -C $S4 rev-parse --short HEAD 2>$null) } catch { }
if (-not $commit) { $commit = 'not a git repo' }

$md = @(
  '# PROVENANCE: files imported from Sprint 4',
  '',
  "Imported $(Get-Date -Format 'yyyy-MM-dd HH:mm') by ``scripts/import_foundation.ps1`` from the Sprint 4 project (commit $commit).",
  'G1 updates the last column ("changed: ...") for every file it adapts.',
  '',
  '| file here | source (Sprint 4) | sha256 (12) | changes |',
  '|---|---|---|---|'
) + $rows
if ($missing.Count -gt 0) { $md += @('', '**Not found in Sprint 4 (G1 must write or skip):** ' + (($missing | ForEach-Object { "``$($_ -replace '\\','/')``" }) -join ', ')) }
Set-Content -Path (Join-Path $Repo 'PROVENANCE.md') -Value $md -Encoding utf8

Write-Host "Imported $($rows.Count) entries from $S4 (commit $commit)."
if ($missing.Count -gt 0) { Write-Host ("Missing: " + ($missing -join ', ')) -ForegroundColor Yellow }
Write-Host "Wrote PROVENANCE.md. Next: review it, then git add -A; git commit -m 'import Sprint 4 foundation'."
