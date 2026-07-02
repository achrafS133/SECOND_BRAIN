# Second Brain - run evaluation benchmarks and save reports
# Usage: .\scripts\run-eval.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Running enterprise QA benchmark..." -ForegroundColor Cyan
second-brain-eval

Write-Host "`nRunning IoT policy benchmark..." -ForegroundColor Cyan
second-brain-iot-eval

Write-Host "`nRunning ablation study (may take several minutes)..." -ForegroundColor Cyan
second-brain-ablation

Write-Host "`nReports written to eval/reports/" -ForegroundColor Green
