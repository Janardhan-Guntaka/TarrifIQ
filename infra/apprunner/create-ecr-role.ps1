# One-time: IAM role so App Runner can pull from ECR (free)
$ErrorActionPreference = "Stop"
$aws = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
$roleName = "AppRunnerECRAccessRole"
$trust = Get-Content "$PSScriptRoot\trust-policy.json" -Raw

try {
    & $aws iam get-role --role-name $roleName | Out-Null
    Write-Host "Role $roleName already exists"
} catch {
    & $aws iam create-role --role-name $roleName --assume-role-policy-document $trust
    & $aws iam attach-role-policy --role-name $roleName `
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
    Write-Host "Created $roleName"
}

$arn = (& $aws iam get-role --role-name $roleName | ConvertFrom-Json).Role.Arn
Write-Host "ECR access role ARN: $arn"
