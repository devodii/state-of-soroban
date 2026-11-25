import argparse
import asyncio
import logging
import os
import time

from state_of_soroban.config import ROOT, get_settings
from state_of_soroban.db_utils import pgschema
from state_of_soroban.db_utils.connection import Connection


def run_schema(args: argparse.Namespace) -> int:
    connection = Connection.from_url(get_settings().database_url)
    match args.action:
        case "apply":
            if not (connection.is_local or args.remote or os.environ.get("CI")):
                print(
                    f"{connection.label} is not on this machine. Pass --remote to "
                    "apply to it."
                )
                return 1
            return pgschema.apply(connection, allow_destructive=args.allow_destructive)
        case "verify":
            return pgschema.verify(connection)
    return 1


async def show_ready() -> int:
    from state_of_soroban.database import open_pool
    from state_of_soroban.readiness import check
    from state_of_soroban.workflow import load_workflow

    pool = await open_pool(2)
    try:
        report = await check(pool, load_workflow())
    finally:
        await pool.close()
    print(report.markdown())
    return 0 if report.ready else 1


def run_stages(args: argparse.Namespace) -> int:
    connection = Connection.from_url(get_settings().database_url)
    if not connection.is_local:
        print(f"{connection.label} is not on this machine.")
        return 1
    from state_of_soroban.runner import run_workflow

    attempt = 0
    while True:
        try:
            asyncio.run(
                run_workflow(args.only, args.skip, args.start, args.force, args.limit)
            )
            return 0
        except ValueError as error:
            print(error)
            return 1
        except Exception:
            if not args.supervise:
                raise
            attempt += 1
            pause = min(30 * attempt, 600)
            logging.getLogger("state_of_soroban").exception(
                "run crashed, resuming from checkpoints in %ss (attempt %s)",
                pause,
                attempt,
            )
            time.sleep(pause)


def main() -> None:
    parser = argparse.ArgumentParser(prog="state-of-soroban")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run the stages of the workflow yaml")
    run.add_argument("--from", dest="start", help="start at this stage and carry on")
    run.add_argument("--only", nargs="+", default=[], help="run only these stages")
    run.add_argument("--skip", nargs="+", default=[], help="leave these stages out")
    run.add_argument("--force", action="store_true", help="redo work already stored")
    run.add_argument("--limit", type=int, help="stop each stage after this many items")
    run.add_argument(
        "--supervise",
        action="store_true",
        help="restart after a crash and resume from the checkpoints",
    )
    commands.add_parser(
        "drive", help="autopilot: run every stage, restart on crashes, follow new work"
    )
    site = commands.add_parser("serve", help="browse the data on a local website")
    site.add_argument("--port", type=int, default=None)
    plan = commands.add_parser(
        "extract-plan", help="publish the repos to scan on the queue branch"
    )
    plan.add_argument("--limit", type=int, default=0)
    shard = commands.add_parser(
        "extract-shard",
        help="clone and analyse one slice of the queue (runs in actions)",
    )
    shard.add_argument("--targets", required=True)
    shard.add_argument("--patterns", required=True)
    shard.add_argument("--index", type=int, required=True)
    shard.add_argument("--count", type=int, required=True)
    shard.add_argument("--out", required=True)
    shard.add_argument("--concurrency", type=int, default=24)
    commands.add_parser(
        "ready",
        help="show whether indexing is complete enough to start the friction layer",
    )
    schema = commands.add_parser("schema", help="manage the database schema")
    actions = schema.add_subparsers(dest="action", required=True)
    apply = actions.add_parser("apply", help="apply the schema files")
    apply.add_argument("--allow-destructive", action="store_true")
    apply.add_argument("--remote", action="store_true")
    actions.add_parser("verify", help="fail unless the database matches the schema")
    args = parser.parse_args()

    (ROOT / "out").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(ROOT / "out" / "pipeline.log"),
        ],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    match args.command:
        case "run":
            raise SystemExit(run_stages(args))
        case "drive":
            from state_of_soroban.drive import drive

            while True:
                try:
                    asyncio.run(drive())
                    break
                except Exception:
                    logging.getLogger("state_of_soroban").exception(
                        "autopilot crashed, restarting in 60s"
                    )
                    time.sleep(60)
        case "extract-plan":
            from state_of_soroban.extract.plan import run_plan

            print(asyncio.run(run_plan(args.limit)))
        case "extract-shard":
            from pathlib import Path

            from state_of_soroban.extract.shard import run_shard

            asyncio.run(
                run_shard(
                    Path(args.targets),
                    Path(args.patterns),
                    args.index,
                    args.count,
                    Path(args.out),
                    args.concurrency,
                )
            )
        case "serve":
            from state_of_soroban.web.server import serve

            serve(args.port)
        case "ready":
            raise SystemExit(asyncio.run(show_ready()))
        case "schema":
            raise SystemExit(run_schema(args))
