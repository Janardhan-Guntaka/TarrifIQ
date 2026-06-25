# TariffIQ — lowest-cost AWS deploy (App Runner minimum tier)
# Prerequisites: AWS CLI configured, Docker running, .env filled at repo root
#
# Cost tips:
#   - App Runner min: 0.25 vCPU / 0.5 GB (~$5-7/mo if left running 24/7)
#   - PAUSE the service in AWS Console when not demoing → stops compute charges
#   - ECR: one small image ≈ free tier; Vercel hobby = free for frontend
#   - Supabase already hosts DB — no extra AWS database cost
#
# ONE-TIME (Console): ECR → Create repository → name: tariffiq-api
#   (ECR PowerUser cannot create repos — use Console or attach ECR FullAccess once)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $Root

$aws = if (Get-Command aws -ErrorAction SilentlyContinue) { "aws" } else { "C:\Program Files\Amazon\AWSCLIV2\aws.exe" }
$Region = "us-east-1"
$RepoName = "tariffiq-api"
$ServiceName = "tariffiq-api"

# ── Account ───────────────────────────────────────────────────────────────────
$account = (& $aws sts get-caller-identity | ConvertFrom-Json).Account
$ecrUri = "${account}.dkr.ecr.${Region}.amazonaws.com/${RepoName}:latest"
Write-Host "Account: $account"
Write-Host "ECR image: $ecrUri"

# ── Verify ECR repo exists ────────────────────────────────────────────────────
try {
    & $aws ecr describe-repositories --repository-names $RepoName --region $Region | Out-Null
} catch {
    Write-Host ""
    Write-Host "ECR repo '$RepoName' not found." -ForegroundColor Red
    Write-Host "Create it once in AWS Console: ECR → Create repository → $RepoName"
    Write-Host "Or attach AmazonEC2ContainerRegistryFullAccess to user tarrifiq temporarily."
    exit 1
}

# ── Docker build & push ───────────────────────────────────────────────────────
Write-Host "`nLogging in to ECR..."
& $aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin "${account}.dkr.ecr.${Region}.amazonaws.com"

Write-Host "Building image..."
docker build -f docker/Dockerfile -t "${RepoName}:latest" .

Write-Host "Pushing to ECR..."
docker tag "${RepoName}:latest" $ecrUri
docker push $ecrUri

# ── App Runner ECR access role ────────────────────────────────────────────────
$roleName = "AppRunnerECRAccessRole"
$trustPath = Join-Path $PSScriptRoot "trust-policy.json"
$trust = Get-Content $trustPath -Raw

try {
    & $aws iam get-role --role-name $roleName | Out-Null
    Write-Host "IAM role $roleName exists"
} catch {
    Write-Host "Creating IAM role $roleName..."
    & $aws iam create-role --role-name $roleName --assume-role-policy-document $trust
    & $aws iam attach-role-policy --role-name $roleName `
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
    Start-Sleep -Seconds 10
}
$accessRoleArn = (& $aws iam get-role --role-name $roleName | ConvertFrom-Json).Role.Arn

# ── Load env from .env (never printed) ───────────────────────────────────────
if (-not (Test-Path ".env")) { throw "Missing .env at repo root" }
$envMap = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $k, $v = $_ -split '=', 2
    $envMap[$k.Trim()] = $v.Trim()
}

# Production DATABASE_URL: build direct connection for AWS
$dbUrl = $envMap["DATABASE_URL"]
if (-not $dbUrl -and $envMap["SUPABASE_DB_PASSWORD"]) {
    $ref = $envMap["SUPABASE_PROJECT_REF"]
    if (-not $ref -and $envMap["SUPABASE_URL"]) {
        $ref = ($envMap["SUPABASE_URL"] -replace "https://", "" -split "\.")[0]
    }
    $pwd = $envMap["SUPABASE_DB_PASSWORD"]
    $dbUrl = "postgresql://postgres:${pwd}@db.${ref}.supabase.co:5432/postgres?sslmode=require"
}

$runtimeEnv = @{
    ENVIRONMENT              = "production"
    DATABASE_URL             = $dbUrl
    OPENAI_API_KEY           = $envMap["OPENAI_API_KEY"]
    SUPABASE_URL             = $envMap["SUPABASE_URL"]
    SUPABASE_ANON_KEY        = $envMap["SUPABASE_ANON_KEY"]
    SUPABASE_SERVICE_ROLE_KEY = $envMap["SUPABASE_SERVICE_ROLE_KEY"]
    SUPABASE_JWT_SECRET      = $envMap["SUPABASE_JWT_SECRET"]
    CORS_ORIGINS             = $(if ($envMap["CORS_ORIGINS"]) { $envMap["CORS_ORIGINS"] } else { "http://localhost:3000" })
    OPENAI_EMBED_MODEL       = $(if ($envMap["OPENAI_EMBED_MODEL"]) { $envMap["OPENAI_EMBED_MODEL"] } else { "text-embedding-3-small" })
    OPENAI_CHAT_MODEL        = $(if ($envMap["OPENAI_CHAT_MODEL"]) { $envMap["OPENAI_CHAT_MODEL"] } else { "gpt-4o-mini" })
    EMBEDDING_DIMENSIONS     = $(if ($envMap["EMBEDDING_DIMENSIONS"]) { $envMap["EMBEDDING_DIMENSIONS"] } else { "1536" })
}

foreach ($key in @("DATABASE_URL", "OPENAI_API_KEY", "SUPABASE_URL")) {
    if (-not $runtimeEnv[$key]) { throw "Missing required .env key: $key" }
}

# ── Create or update App Runner (minimum instance size) ─────────────────────────
$sourceConfig = @{
    ImageRepository = @{
        ImageIdentifier     = $ecrUri
        ImageRepositoryType = "ECR"
        ImageConfiguration  = @{
            Port                        = "8000"
            RuntimeEnvironmentVariables = $runtimeEnv
        }
    }
    AuthenticationConfiguration = @{ AccessRoleArn = $accessRoleArn }
    AutoDeploymentsEnabled      = $false
} | ConvertTo-Json -Depth 6 -Compress

$instanceConfig = '{"Cpu":"0.25 vCPU","Memory":"0.5 GB"}'
$healthConfig = '{"Protocol":"HTTP","Path":"/health","Interval":20,"Timeout":5,"HealthyThreshold":1,"UnhealthyThreshold":5}'

$existing = & $aws apprunner list-services --region $Region | ConvertFrom-Json
$svc = $existing.ServiceSummaryList | Where-Object { $_.ServiceName -eq $ServiceName } | Select-Object -First 1

if ($svc) {
    Write-Host "`nUpdating existing App Runner service..."
    & $aws apprunner update-service --region $Region `
        --service-arn $svc.ServiceArn `
        --source-configuration $sourceConfig `
        --instance-configuration $instanceConfig `
        --health-check-configuration $healthConfig | Out-Null
    & $aws apprunner start-deployment --region $Region --service-arn $svc.ServiceArn | Out-Null
    $arn = $svc.ServiceArn
} else {
    Write-Host "`nCreating App Runner service (min cost: 0.25 vCPU / 0.5 GB)..."
    $result = & $aws apprunner create-service --region $Region `
        --service-name $ServiceName `
        --source-configuration $sourceConfig `
        --instance-configuration $instanceConfig `
        --health-check-configuration $healthConfig | ConvertFrom-Json
    $arn = $result.Service.ServiceArn
}

Write-Host "Waiting for service to become running (2-5 min)..."
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 15
    $desc = & $aws apprunner describe-service --region $Region --service-arn $arn | ConvertFrom-Json
    $status = $desc.Service.Status
    Write-Host "  Status: $status"
    if ($status -eq "RUNNING") {
        $url = $desc.Service.ServiceUrl
        Write-Host ""
        Write-Host "API live: https://$url" -ForegroundColor Green
        Write-Host "Health:   https://$url/health"
        Write-Host ""
        Write-Host "Next — Vercel:"
        Write-Host "  NEXT_PUBLIC_API_URL=https://$url"
        Write-Host "Then add Vercel URL to CORS_ORIGINS and re-run this script."
        Write-Host ""
        Write-Host "Save costs: pause service in Console when not in use."
        exit 0
    }
    if ($status -in @("CREATE_FAILED", "UPDATE_FAILED", "DELETE_FAILED")) {
        throw "App Runner failed: $status"
    }
}
Write-Host "Still starting. Check AWS Console → App Runner → $ServiceName"
Write-Host "Service ARN: $arn"
