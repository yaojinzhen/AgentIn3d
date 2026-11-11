"""Model, preview, export and inspect assets without a governance workflow."""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

from inf_agent.execution.doctor import host_doctor_report
from inf_agent.execution.resource_policy import ResourceLimitError
from inf_agent.workspace.input_validation import InputValidationError
from inf_agent.execution.service import REPO_ROOT, run_workspace, validate_run
from inf_agent.indexing.query import (
    DEFAULT_DOCUMENT_LIMIT,
    DOCUMENT_DOMAINS,
    IndexQueryError,
    documentation_query_result,
)
from inf_agent.knowledge.resolver import read_knowledge
from inf_agent.knowledge.verification import inspect_source
from inf_agent.workspace.contracts import (
    ASSET_OUTPUTS_ROOT,
    PRODUCT_VERSION,
    ContractError,
    load_json,
    validate_asset_id,
)
from inf_agent.workspace.manager import create_workspace, workspace_status


def _resolution(value: str) -> tuple[int, int]:
    try:
        width, height = map(int, value.lower().split("x"))
        if min(width, height) < 16:
            raise ValueError()
        return width, height
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "resolution must use WIDTHxHEIGHT, each >=16"
        ) from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=PRODUCT_VERSION)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser(
        "start", help="Create a new workspace; existing folders are never overwritten"
    )
    location = start.add_mutually_exclusive_group(required=True)
    location.add_argument("--workspace", type=Path)
    location.add_argument("--asset-id")
    start.add_argument("--base-dir", type=Path, default=ASSET_OUTPUTS_ROOT)
    prompts = start.add_mutually_exclusive_group(required=True)
    prompts.add_argument("--prompt")
    prompts.add_argument("--prompt-file", type=Path)
    start.add_argument("--image", type=Path)
    for name in ("width", "depth", "height"):
        start.add_argument(f"--{name}", type=float)
    start.add_argument("--forbid", action="append", default=[])
    query = sub.add_parser(
        "query", help="Find modeling knowledge independently of any task"
    )
    query.add_argument("domain", choices=DOCUMENT_DOMAINS)
    query.add_argument("--query", "-q", required=True)
    query.add_argument("--limit", type=int, default=DEFAULT_DOCUMENT_LIMIT)
    query.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    read = sub.add_parser(
        "read", help="Read a modeling document or exact repository source symbol"
    )
    leaf = read.add_mutually_exclusive_group(required=True)
    leaf.add_argument("--document")
    leaf.add_argument("--symbol")
    read.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    lint = sub.add_parser(
        "lint", help="Report syntax and known API compatibility diagnostics"
    )
    lint.add_argument("--source", type=Path, required=True)
    for command in ("preview", "export"):
        run = sub.add_parser(
            command, help="Run current source into a new isolated output folder"
        )
        run.add_argument("--workspace", type=Path, required=True)
        run.add_argument("--factory", help="Optional class name from asset.py")
        run.add_argument("--seed", type=int, default=0)
        run.add_argument("--instance-index", type=int, default=0)
        run.add_argument("--resolution", type=_resolution, default=(512, 512))
        run.add_argument("--samples", type=int, default=32)
        if command == "export":
            run.add_argument(
                "--texture-resolution",
                type=int,
                default=2048,
                help="Baked GLB texture size, 64-4096 (default 2048)",
            )
            run.add_argument(
                "--bake-samples",
                type=int,
                default=4,
                help="Cycles CPU texture bake samples, 1-128 (default 4)",
            )
        run.add_argument(
            "--render", action=argparse.BooleanOptionalAction, default=True
        )
        run.add_argument(
            "--limits",
            type=Path,
            help="JSON overrides for implemented ResourcePolicy fields",
        )
    validate = sub.add_parser(
        "validate", help="Revalidate a current-format run and its artifacts"
    )
    validate.add_argument("--run", type=Path, required=True)
    status = sub.add_parser("status", help="Read input and latest run results")
    status.add_argument("--workspace", type=Path, required=True)
    sub.add_parser(
        "doctor", help="Explicit Blender save/export/reopen environment diagnostic"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "start":
            if args.asset_id:
                validate_asset_id(args.asset_id)
            workspace = args.workspace or args.base_dir / args.asset_id
            prompt = (
                args.prompt
                if args.prompt is not None
                else args.prompt_file.read_text(encoding="utf-8")
            )
            result = create_workspace(
                workspace,
                prompt=prompt,
                image=args.image,
                dimensions={
                    name: getattr(args, name)
                    for name in ("width", "depth", "height")
                    if getattr(args, name) is not None
                },
                forbidden=args.forbid,
            )
        elif args.command == "query":
            result = documentation_query_result(
                args.repo_root, args.domain, args.query, limit=args.limit
            )
        elif args.command == "read":
            result = read_knowledge(
                args.repo_root, document=args.document, symbol=args.symbol
            )
        elif args.command == "lint":
            result = inspect_source(args.source)
        elif args.command in {"preview", "export"}:
            result = run_workspace(
                args.workspace,
                factory=args.factory,
                seed=args.seed,
                instance_index=args.instance_index,
                render=args.render,
                export_glb=args.command == "export",
                resolution=args.resolution,
                samples=args.samples,
                texture_resolution=getattr(args, "texture_resolution", 2048),
                bake_samples=getattr(args, "bake_samples", 4),
                limits=load_json(args.limits) if args.limits else None,
            )
        elif args.command == "validate":
            result = validate_run(args.run)
        elif args.command == "status":
            result = workspace_status(args.workspace)
        else:
            result = host_doctor_report(REPO_ROOT)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        if "objective_success" in result:
            return 0 if result["objective_success"] else 1
        if args.command == "doctor":
            return 0 if result["status"] == "READY" else 1
        return 0 if result.get("success", True) else 1
    except (
        OSError,
        ContractError,
        InputValidationError,
        ResourceLimitError,
        IndexQueryError,
        SyntaxError,
    ) as error:
        print(
            json.dumps(
                {"success": False, "error": f"{type(error).__name__}: {error}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    from inf_agent.execution.run_asset import _exit

    _exit(main())
