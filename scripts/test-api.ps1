# Second Brain - API integration test script
# Usage:
#   .\scripts\test-api.ps1
#   .\scripts\test-api.ps1 -Port 8090
#   .\scripts\test-api.ps1 -Port 8090 -SkipAnomaly

param(
    [int]$Port = 8090,
    [switch]$SkipAnomaly,
    [switch]$ApproveAction
)

$BaseUrl = "http://localhost:$Port"
$Passed = 0
$Failed = 0

function Write-Result {
    param([string]$Name, [bool]$Ok, [string]$Detail = "")
    if ($Ok) {
        Write-Host "  [PASS] $Name" -ForegroundColor Green
        if ($Detail) { Write-Host "         $Detail" -ForegroundColor DarkGray }
        $script:Passed++
    } else {
        Write-Host "  [FAIL] $Name" -ForegroundColor Red
        if ($Detail) { Write-Host "         $Detail" -ForegroundColor Yellow }
        $script:Failed++
    }
}

function Invoke-Api {
    param(
        [string]$Method = "GET",
        [string]$Path,
        [object]$Body = $null,
        [int]$TimeoutSec = 120
    )
    $uri = "$BaseUrl$Path"
    $params = @{
        Uri             = $uri
        Method          = $Method
        UseBasicParsing = $true
        TimeoutSec      = $TimeoutSec
    }
    if ($Body -ne $null) {
        $params.ContentType = "application/json"
        $params.Body = ($Body | ConvertTo-Json -Depth 6 -Compress)
    }
    return Invoke-WebRequest @params
}

Write-Host ""
Write-Host "Second Brain API Tests" -ForegroundColor Cyan
Write-Host "Target: $BaseUrl" -ForegroundColor DarkGray
Write-Host ("-" * 50)

function Write-Step { param([string]$Msg) Write-Host "  > $Msg" -ForegroundColor DarkGray }

# 1. Health
Write-Step "Checking /health ..."
try {
    $health = (Invoke-Api -Path "/health").Content | ConvertFrom-Json
    $svc = $health.services
    $allUp = $health.status -eq "ok" -and $svc.redis -and $svc.neo4j -and $svc.kafka
    $llmInfo = if ($health.llm_provider) {
        "$($health.llm_provider) / $($health.llm_model)"
    } else {
        "configured=$($health.llm_configured)"
    }
    Write-Result "Health check" $allUp "LLM: $llmInfo | Redis=$($svc.redis) Neo4j=$($svc.neo4j) Kafka=$($svc.kafka)"
} catch {
    Write-Result "Health check" $false $_.Exception.Message
    Write-Host ""
    Write-Host "Is the API running? Start with:" -ForegroundColor Yellow
    Write-Host "  python -m uvicorn second_brain.api.main:app --host 0.0.0.0 --port $Port" -ForegroundColor White
    exit 1
}

# 2. Dashboard
Write-Step "Loading dashboard ..."
try {
    $dash = Invoke-Api -Path "/static/index.html" -TimeoutSec 30
    $ok = $dash.StatusCode -eq 200 -and $dash.Content -match "Second Brain"
    Write-Result "Dashboard (/static/index.html)" $ok "HTTP $($dash.StatusCode), $($dash.Content.Length) bytes"
} catch {
    Write-Result "Dashboard" $false $_.Exception.Message
}

# 3. Root redirect
Write-Step "Checking / redirect ..."
try {
    $curlOut = curl.exe -s -o NUL -w "%{http_code} %{redirect_url}" "$BaseUrl/" 2>$null
    $parts = $curlOut -split " ", 2
    $code = $parts[0]
    $location = if ($parts.Count -gt 1) { $parts[1] } else { "" }
    $ok = $code -match "^30[1278]$" -and $location -match "index.html"
    Write-Result "Root redirect (/) -> dashboard" $ok $location
} catch {
    Write-Result "Root redirect" $false $_.Exception.Message
}

# 4. Query (LLM)
Write-Step "POST /query (NVIDIA LLM, may take 30-90s) ..."
try {
    $queryBody = @{
        query      = "What is M0 memory?"
        session_id = "script-test-$(Get-Date -Format 'HHmmss')"
        task_type  = "qa"
    }
    $q = (Invoke-Api -Method POST -Path "/query" -Body $queryBody -TimeoutSec 180).Content | ConvertFrom-Json
    $isLlm = $q.plan -contains "LLM synthesis with retrieved context"
    $hasAnswer = $q.answer.Length -gt 20
    $ok = $hasAnswer -and $q.critic_verdict -eq "accept"
    $preview = if ($q.answer.Length -gt 120) { $q.answer.Substring(0, 120) + "..." } else { $q.answer }
    Write-Result "Query (POST /query)" $ok $preview
    if (-not $isLlm) {
        Write-Host "         Warning: heuristic fallback (check LLM_PROVIDER in .env)" -ForegroundColor Yellow
    }
} catch {
    Write-Result "Query" $false $_.Exception.Message
}

# 5. Document ingest
Write-Step "POST /ingest/document ..."
try {
    $docBody = @{
        uri     = "doc://script/test-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        title   = "Script Test Document"
        content = "M0 working memory handles IoT streams. M1 is short-term context. M2 is Neo4j long-term storage."
    }
    $ing = (Invoke-Api -Method POST -Path "/ingest/document" -Body $docBody).Content | ConvertFrom-Json
    $ok = $ing.status -eq "ingested" -and $ing.chunk_count -ge 1
    Write-Result "Ingest (POST /ingest/document)" $ok "$($ing.chunk_count) chunk(s)"
} catch {
    Write-Result "Ingest" $false $_.Exception.Message
}

# 6. IoT anomaly flow
if (-not $SkipAnomaly) {
    Write-Step "POST /stream/iot warmup + anomaly (LLM, may take 1-3 min) ..."
    try {
        $deviceId = "script-hvac-$(Get-Random -Maximum 9999)"
        $warmup = @(20.0, 20.1, 20.0, 20.2, 20.1, 20.0, 20.1)
        foreach ($v in $warmup) {
            $null = Invoke-Api -Method POST -Path "/stream/iot" -Body @{
                device_id = $deviceId
                zone_id   = "zone-a"
                metric    = "temperature"
                value     = $v
            } -TimeoutSec 60
        }
        $iot = (Invoke-Api -Method POST -Path "/stream/iot" -Body @{
            device_id = $deviceId
            zone_id   = "zone-a"
            metric    = "temperature"
            value     = 45.0
        } -TimeoutSec 300).Content | ConvertFrom-Json

        $ok = $iot.anomaly_detected -eq $true -and $null -ne $iot.pending_action_id
        Write-Result "IoT anomaly (POST /stream/iot)" $ok "device=$deviceId pending=$($iot.pending_action_id)"

        # 7. Pending actions
        $pending = (Invoke-Api -Path "/actions/pending").Content | ConvertFrom-Json
        $hasPending = @($pending).Count -gt 0
        Write-Result "Pending actions (GET /actions/pending)" $hasPending "$(@($pending).Count) action(s)"

        # 8. Optional approve first pending action
        if ($ApproveAction -and $hasPending) {
            $actionId = $pending[0].id
            $decision = (Invoke-Api -Method POST -Path "/actions/$actionId/approve" -Body @{
                approved = $true
                reviewer = "test-script"
                note     = "Auto-approved by test-api.ps1"
            }).Content | ConvertFrom-Json
            $ok = $decision.status -eq "executed" -or $decision.status -eq "approved"
            Write-Result "Approve action (POST /actions/{id}/approve)" $ok "status=$($decision.status)"
        }
    } catch {
        Write-Result "IoT anomaly flow" $false $_.Exception.Message
    }
} else {
    Write-Host "  [SKIP] IoT anomaly flow (-SkipAnomaly)" -ForegroundColor DarkGray
}

# Summary
Write-Host ("-" * 50)
$total = $Passed + $Failed
if ($Failed -eq 0) {
    Write-Host "All $total test(s) passed." -ForegroundColor Green
    Write-Host "Dashboard: $BaseUrl/" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "$Passed passed, $Failed failed (of $total)." -ForegroundColor Red
    exit 1
}
