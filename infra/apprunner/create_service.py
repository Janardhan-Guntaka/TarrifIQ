"""One-shot App Runner create/update using JSON files (avoids PowerShell JSON issues)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AWS = r"C:\Program Files\Amazon\AWSCLIV2\aws.exe"
REGION = "us-east-1"
ACCOUNT = "885740665912"
REPO = "tariffiq-api"
SERVICE = "tariffiq-api"
ECR_URI = f"{ACCOUNT}.dkr.ecr.{REGION}.amazonaws.com/{REPO}:latest"
ROLE_NAME = "AppRunnerECRAccessRole"
TRUST = Path(__file__).parent / "trust-policy.json"


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd[:6]), "...")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def load_env() -> dict[str, str]:
    env_path = ROOT / ".env"
    if not env_path.exists():
        sys.exit("Missing .env at repo root")
    out: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def database_url(env: dict[str, str]) -> str:
    if env.get("DATABASE_URL"):
        return env["DATABASE_URL"]
    pwd = env.get("SUPABASE_DB_PASSWORD")
    ref = env.get("SUPABASE_PROJECT_REF")
    if not ref and env.get("SUPABASE_URL"):
        ref = env["SUPABASE_URL"].replace("https://", "").split(".")[0]
    if pwd and ref:
        return f"postgresql://postgres:{pwd}@db.{ref}.supabase.co:5432/postgres?sslmode=require"
    sys.exit("Need DATABASE_URL or SUPABASE_DB_PASSWORD + project ref")


def ensure_ecr_role() -> str:
    r = run([AWS, "iam", "get-role", "--role-name", ROLE_NAME], check=False)
    if r.returncode == 0:
        return json.loads(r.stdout)["Role"]["Arn"]
    trust = TRUST.read_text(encoding="utf-8")
    run([AWS, "iam", "create-role", "--role-name", ROLE_NAME, "--assume-role-policy-document", trust])
    run(
        [
            AWS,
            "iam",
            "attach-role-policy",
            "--role-name",
            ROLE_NAME,
            "--policy-arn",
            "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess",
        ]
    )
    time.sleep(10)
    r = run([AWS, "iam", "get-role", "--role-name", ROLE_NAME])
    return json.loads(r.stdout)["Role"]["Arn"]


def build_configs(access_role_arn: str, env: dict[str, str]) -> tuple[Path, Path, Path]:
    tmp = Path(__file__).parent / ".tmp"
    tmp.mkdir(exist_ok=True)
    runtime = {
        "ENVIRONMENT": "production",
        "DATABASE_URL": database_url(env),
        "OPENAI_API_KEY": env["OPENAI_API_KEY"],
        "SUPABASE_URL": env["SUPABASE_URL"],
        "SUPABASE_ANON_KEY": env["SUPABASE_ANON_KEY"],
        "SUPABASE_SERVICE_ROLE_KEY": env["SUPABASE_SERVICE_ROLE_KEY"],
        "SUPABASE_JWT_SECRET": env["SUPABASE_JWT_SECRET"],
        "CORS_ORIGINS": env.get("CORS_ORIGINS", "http://localhost:3000"),
        "OPENAI_EMBED_MODEL": env.get("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
        "OPENAI_CHAT_MODEL": env.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        "EMBEDDING_DIMENSIONS": env.get("EMBEDDING_DIMENSIONS", "1536"),
    }
    for key in ("DATABASE_URL", "OPENAI_API_KEY", "SUPABASE_URL"):
        if not runtime.get(key):
            sys.exit(f"Missing required .env key: {key}")

    source = {
        "ImageRepository": {
            "ImageIdentifier": ECR_URI,
            "ImageRepositoryType": "ECR",
            "ImageConfiguration": {
                "Port": "8000",
                "RuntimeEnvironmentVariables": runtime,
            },
        },
        "AuthenticationConfiguration": {"AccessRoleArn": access_role_arn},
        "AutoDeploymentsEnabled": False,
    }
    instance = {"Cpu": "0.25 vCPU", "Memory": "0.5 GB"}
    health = {
        "Protocol": "HTTP",
        "Path": "/health",
        "Interval": 20,
        "Timeout": 5,
        "HealthyThreshold": 1,
        "UnhealthyThreshold": 5,
    }
    source_path = tmp / "source-config.json"
    instance_path = tmp / "instance-config.json"
    health_path = tmp / "health-config.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    instance_path.write_text(json.dumps(instance), encoding="utf-8")
    health_path.write_text(json.dumps(health), encoding="utf-8")
    return source_path, instance_path, health_path


def main() -> None:
    env = load_env()
    role_arn = ensure_ecr_role()
    print(f"ECR access role: {role_arn}")
    source, instance, health = build_configs(role_arn, env)

    r = run([AWS, "apprunner", "list-services", "--region", REGION])
    services = json.loads(r.stdout).get("ServiceSummaryList", [])
    existing = next((s for s in services if s.get("ServiceName") == SERVICE), None)

    if existing:
        arn = existing["ServiceArn"]
        print(f"Updating service {arn}")
        run(
            [
                AWS,
                "apprunner",
                "update-service",
                "--region",
                REGION,
                "--service-arn",
                arn,
                "--source-configuration",
                f"file://{source.as_posix()}",
                "--instance-configuration",
                f"file://{instance.as_posix()}",
                "--health-check-configuration",
                f"file://{health.as_posix()}",
            ]
        )
        run([AWS, "apprunner", "start-deployment", "--region", REGION, "--service-arn", arn])
    else:
        print("Creating App Runner service...")
        r = run(
            [
                AWS,
                "apprunner",
                "create-service",
                "--region",
                REGION,
                "--service-name",
                SERVICE,
                "--source-configuration",
                f"file://{source.as_posix()}",
                "--instance-configuration",
                f"file://{instance.as_posix()}",
                "--health-check-configuration",
                f"file://{health.as_posix()}",
            ]
        )
        arn = json.loads(r.stdout)["Service"]["ServiceArn"]
        print(f"Service ARN: {arn}")

    print("Waiting for RUNNING...")
    for _ in range(40):
        time.sleep(15)
        r = run([AWS, "apprunner", "describe-service", "--region", REGION, "--service-arn", arn])
        svc = json.loads(r.stdout)["Service"]
        status = svc["Status"]
        print(f"  Status: {status}")
        if status == "RUNNING":
            url = svc["ServiceUrl"]
            print(f"\nAPI_URL=https://{url}")
            print(f"HEALTH=https://{url}/health")
            print(f"SERVICE_ARN={arn}")
            return
        if status in ("CREATE_FAILED", "UPDATE_FAILED", "DELETE_FAILED"):
            sys.exit(f"App Runner failed: {status}")
    print("Still starting — check AWS Console → App Runner")


if __name__ == "__main__":
    main()
