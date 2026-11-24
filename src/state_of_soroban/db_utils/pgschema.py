import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel

from state_of_soroban.config import ROOT, get_settings
from state_of_soroban.db_utils.connection import Connection
from state_of_soroban.db_utils.guard import destructive_statements
from state_of_soroban.db_utils.manifest import generate_manifest, manifest_text

API_DIR = ROOT
MANIFEST = "/db/schema/manifest.sql"
LOCK_TIMEOUT = "30s"


class Target(BaseModel, frozen=True):
    """One database and the schema files that describe it."""

    name: str
    db_dir: Path

    @property
    def schema_dir(self) -> Path:
        return self.db_dir / "schema"


SCHEMA = Target(name="soroban", db_dir=ROOT / "db")


def docker_command(
    command: str,
    *args: str,
    connection: Connection,
    mounts: dict[Path, str],
    image: str,
) -> list[str]:
    network, host = connection.container_route()
    mount_flags = [
        flag
        for source, target in mounts.items()
        for flag in ("-v", f"{source}:{target}")
    ]
    return [
        "docker",
        "run",
        "--rm",
        "-i",
        *network,
        "-e",
        "PGPASSWORD",
        *mount_flags,
        image,
        command,
        "--host",
        host,
        "--port",
        str(connection.port),
        "--db",
        connection.database,
        "--user",
        connection.user,
        "--schema",
        "public",
        "--sslmode",
        connection.sslmode,
        *args,
    ]


def run_pgschema(
    command: str,
    *args: str,
    connection: Connection,
    target: Target = SCHEMA,
    mounts: dict[Path, str] | None = None,
) -> int:
    cmd = docker_command(
        command,
        *args,
        connection=connection,
        mounts={target.db_dir: "/db", **(mounts or {})},
        image=get_settings().pgschema_image,
    )
    env = {**os.environ, "PGPASSWORD": connection.password}
    return subprocess.run(cmd, env=env, check=False).returncode


def format_schema(target: Target = SCHEMA) -> None:
    """Fix what sqlfluff can, then lint so what is left shows its file and rule."""
    for action in ("fix", "lint"):
        subprocess.run(
            [sys.executable, "-m", "sqlfluff", action, str(target.schema_dir)],
            cwd=API_DIR,
            check=False,
        )


def plan_sql(
    connection: Connection, out_dir: Path, target: Target = SCHEMA
) -> tuple[int, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.chmod(0o777)
    returncode = run_pgschema(
        "plan",
        "--file",
        MANIFEST,
        "--output-json",
        "/out/plan.json",
        "--output-sql",
        "/out/plan.sql",
        connection=connection,
        target=target,
        mounts={out_dir: "/out"},
    )
    sql_file = out_dir / "plan.sql"
    return returncode, sql_file.read_text() if sql_file.is_file() else ""


def apply(
    connection: Connection,
    *,
    allow_destructive: bool = False,
    out_dir: Path | None = None,
    target: Target = SCHEMA,
) -> int:
    generate_manifest(target.schema_dir)
    with TemporaryDirectory() as scratch:
        work_dir = out_dir or Path(scratch)
        work_dir.mkdir(parents=True, exist_ok=True)
        returncode, sql = plan_sql(connection, work_dir, target)
        if returncode != 0:
            return returncode
        if not sql.strip():
            print(f"No changes: {connection.label} already matches the schema files.")
            return 0
        print(f"Pending changes for {connection.label}:\n\n{sql}")
        findings = destructive_statements(sql)
        if findings and not allow_destructive:
            print("Refusing to apply: the plan could lose data.", file=sys.stderr)
            for finding in findings:
                print(f"  {finding.reason}: {finding.statement}", file=sys.stderr)
            return 2
        return run_pgschema(
            "apply",
            "--plan",
            "/out/plan.json",
            "--auto-approve",
            "--lock-timeout",
            LOCK_TIMEOUT,
            connection=connection,
            target=target,
            mounts={work_dir: "/out"},
        )


def verify(connection: Connection, target: Target = SCHEMA) -> int:
    manifest = target.schema_dir / "manifest.sql"
    if not manifest.is_file() or manifest.read_text() != manifest_text(
        target.schema_dir
    ):
        print(
            "manifest.sql is out of date: run `state-of-soroban schema plan`.",
            file=sys.stderr,
        )
        return 1
    with TemporaryDirectory() as scratch:
        returncode, sql = plan_sql(connection, Path(scratch), target)
    if returncode != 0:
        return returncode
    if sql.strip():
        print(
            f"{connection.label} differs from the schema files:\n\n{sql}",
            file=sys.stderr,
        )
        return 1
    print(f"In sync: {connection.label} matches the schema files.")
    return 0
