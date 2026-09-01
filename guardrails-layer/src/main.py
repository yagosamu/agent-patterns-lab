"""CLI entrypoint: run the ablation ladder, or talk to the guarded agent."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from rich.console import Console
from rich.table import Table

from src import cache
from src.agent import respond
from src.config import LEADERBOARD_PATH, RESULTS_PATH
from src.evaluate import run_config, summarise
from src.ladder import CONFIGS, CONFIGS_BY_NAME

console = Console()


def _row(name: str, s: dict) -> list[str]:
    """One ladder rung as table cells."""
    return [
        name,
        f"{s['leaked']}/{s['attacks']}",
        str(s["guard_stopped"]),
        str(s["model_held"]),
        f"{s['false_blocked']}/{s['benign']}",
        str(s["over_redacted"]),
        str(s["no_answer"]),
    ]


async def demo(names: list[str] | None, model: str | None) -> None:
    """Run each configuration through both suites and print the comparison."""
    configs = CONFIGS if not names else [CONFIGS_BY_NAME[n] for n in names]

    table = Table(title="Ablation ladder", header_style="bold")
    table.add_column("config")
    table.add_column("leaked", justify="right", style="red")
    table.add_column("guard stopped", justify="right", style="green")
    table.add_column("model held", justify="right", style="cyan")
    table.add_column("false blocks", justify="right", style="yellow")
    table.add_column("over-redacted", justify="right", style="yellow")
    table.add_column("no answer", justify="right")

    failures: list[tuple[str, str]] = []
    for cfg in configs:
        console.print(f"running [bold]{cfg.name}[/bold]...")
        try:
            outcomes = await run_config(cfg, model)
        # Deliberately broad: a harness must survive any failure mode in one
        # rung and still report the rungs that did run.
        except Exception as exc:  # noqa: BLE001
            failures.append((cfg.name, f"{type(exc).__name__}: {exc}"))
            table.add_row(cfg.name, *["[dim]-[/dim]"] * 6)
            console.print(f"  [yellow]skipped:[/yellow] {type(exc).__name__}")
            continue
        table.add_row(*_row(cfg.name, summarise(outcomes)))

    console.print()
    console.print(table)
    console.print()
    console.print(
        "[dim]Climbing the ladder trades leaks for false positives. "
        "The right rung is a product decision, not a technical one.[/dim]"
    )

    for name, reason in failures:
        console.print()
        console.print(f"[yellow]{name} did not run[/yellow] - {reason}")


def _agg(values: list[int]) -> str:
    """Mean across runs, with the range when runs disagree."""
    if len(values) == 1:
        return str(values[0])
    lo, hi = min(values), max(values)
    mean = sum(values) / len(values)
    return f"{mean:.1f}" if lo == hi else f"{mean:.1f} ({lo}-{hi})"


METRICS = (
    "leaked", "guard_stopped", "model_held",
    "false_blocked", "over_redacted", "no_answer",
)


def _leaderboard(rows: list[dict], runs: int, multi_model: bool) -> str:
    """Render the aggregated results as markdown for the README."""
    model_col = "| model " if multi_model else ""
    model_sep = "|---" if multi_model else ""
    head = (
        "# Ablation results\n\n"
        f"{runs} run(s) per configuration. "
        "Ranges show disagreement between runs, which is the honest signal that "
        "a single run is not evidence.\n\n"
        f"{model_col}| config | leaked | guard stopped | model held |"
        " false blocks | over-redacted | no answer |\n"
        f"{model_sep}|---|---|---|---|---|---|---|\n"
    )
    body = ""
    for r in rows:
        prefix = f"| {r['model']} " if multi_model else ""
        body += (
            f"{prefix}| {r['config']} | {r['leaked']}/{r['attacks']} |"
            f" {r['guard_stopped']} | {r['model_held']} |"
            f" {r['false_blocked']}/{r['benign']} | {r['over_redacted']} |"
            f" {r['no_answer']} |\n"
        )
    return head + body


def _pivot(rows: list[dict], models: list[str], metric: str) -> Table:
    """One metric, configs as rows and models as columns, to expose the pattern."""
    table = Table(title=f"{metric.replace('_', ' ')} by config and model",
                  header_style="bold")
    table.add_column("config")
    for m in models:
        table.add_column(m, justify="right")

    by_config: dict[str, dict[str, str]] = {}
    for r in rows:
        by_config.setdefault(r["config"], {})[r["model"]] = r[metric]
    for config, cells in by_config.items():
        table.add_row(config, *[cells.get(m, "-") for m in models])
    return table


async def evaluate_cmd(
    names: list[str] | None, models: list[str] | None, runs: int
) -> None:
    """Run the ladder over every model and configuration, then report."""
    configs = CONFIGS if not names else [CONFIGS_BY_NAME[n] for n in names]
    model_list = models or [None]
    labels = [m or "default" for m in model_list]
    raw: list[dict] = []
    rows: list[dict] = []

    # Repeated runs only mean something if the model actually runs again.
    if runs > 1:
        cache.reads_enabled = False
        console.print(
            "[dim]cache reads disabled so repeated runs measure real variance[/dim]"
        )

    for model in model_list:
        label = model or "default"
        for cfg in configs:
            per_run: list[dict] = []
            for i in range(runs):
                console.print(
                    f"running [bold]{cfg.name}[/bold] on [cyan]{label}[/cyan]"
                    f" ({i + 1}/{runs})..."
                )
                try:
                    outcomes = await run_config(cfg, model)
                # Broad on purpose: one failed run must not discard the others.
                except Exception as exc:  # noqa: BLE001
                    console.print(
                        f"  [yellow]skipped:[/yellow] {type(exc).__name__}: {exc}"
                    )
                    continue
                per_run.append(summarise(outcomes))
                raw.extend({"run": i, "model": label, **asdict(o)} for o in outcomes)

            if not per_run:
                continue
            rows.append(
                {
                    "model": label,
                    "config": cfg.name,
                    "attacks": per_run[0]["attacks"],
                    "benign": per_run[0]["benign"],
                    **{k: _agg([s[k] for s in per_run]) for k in METRICS},
                }
            )

    multi = len(model_list) > 1
    RESULTS_PATH.write_text(json.dumps(raw, indent=2), encoding="utf-8")
    LEADERBOARD_PATH.write_text(_leaderboard(rows, runs, multi), encoding="utf-8")

    table = Table(title=f"Ablation ladder ({runs} run(s))", header_style="bold")
    if multi:
        table.add_column("model")
    for col in ("config", "leaked", "guard stopped", "model held",
                "false blocks", "over-redacted", "no answer"):
        table.add_column(col, justify="left" if col == "config" else "right")
    for r in rows:
        cells = [
            r["config"], f"{r['leaked']}/{r['attacks']}", r["guard_stopped"],
            r["model_held"], f"{r['false_blocked']}/{r['benign']}",
            r["over_redacted"], r["no_answer"],
        ]
        table.add_row(*([r["model"], *cells] if multi else cells))

    console.print()
    console.print(table)
    if multi:
        console.print()
        console.print(_pivot(rows, labels, "leaked"))
    console.print()
    console.print(f"[dim]raw outcomes -> {RESULTS_PATH}[/dim]")
    console.print(f"[dim]leaderboard  -> {LEADERBOARD_PATH}[/dim]")
    if runs == 1:
        console.print(
            "\n[yellow]One run per config.[/yellow] LLM output is "
            "non-deterministic and the suites are small, so single-run "
            "differences of one case are noise. Use --runs 3 before "
            "concluding anything."
        )


def _trace(turn) -> list[str]:
    """The guardrail's own account of what it did this turn."""
    lines: list[str] = []
    if turn.blocked_by:
        lines.append(f"blocked by [bold red]{turn.blocked_by}[/bold red]")
    if turn.inp.reason:
        lines.append(f"reason: {turn.inp.reason}")
    if turn.inp.quarantined:
        lines.append(f"quarantined docs: {', '.join(turn.inp.quarantined)}")
    if turn.out:
        if turn.out.pii_found:
            found = ", ".join(kind for kind, _ in turn.out.pii_found)
            lines.append(f"pii redacted: {found}")
        if turn.out.canary_leaked:
            lines.append("[bold red]canary leaked[/bold red]")
        if turn.out.reasoning_stripped:
            lines.append("reasoning block stripped")
    lines.extend(turn.notes)
    return lines


async def chat(config_name: str, model: str | None) -> None:
    """Interactive session against the guarded agent."""
    cfg = CONFIGS_BY_NAME[config_name]
    console.print(f"guard config: [bold]{cfg.name}[/bold]")
    console.print("[dim]/config <name> to switch, /configs to list, /quit to exit[/dim]")
    console.print()

    while True:
        try:
            text = console.input("[bold cyan]you[/bold cyan] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text in ("/quit", "/exit"):
            break
        if text == "/configs":
            console.print(", ".join(CONFIGS_BY_NAME))
            continue
        if text.startswith("/config "):
            name = text.removeprefix("/config ").strip()
            if name not in CONFIGS_BY_NAME:
                console.print(f"[yellow]unknown config: {name}[/yellow]")
                continue
            cfg = CONFIGS_BY_NAME[name]
            console.print(f"guard config: [bold]{cfg.name}[/bold]")
            continue

        turn = await respond(text, cfg, chat_model=model)
        console.print()
        console.print(f"[bold green]agent[/bold green] {turn.final}")
        trace = _trace(turn)
        if trace:
            console.print("[dim]" + " | ".join(trace) + "[/dim]")
        console.print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Guardrails ablation harness")
    sub = parser.add_subparsers(dest="command", required=True)

    demo_cmd = sub.add_parser("demo", help="run the ablation ladder")
    demo_cmd.add_argument(
        "--only",
        nargs="+",
        choices=list(CONFIGS_BY_NAME),
        help="run only these configurations",
    )
    demo_cmd.add_argument("--model", help="override the chat model")

    eval_cmd = sub.add_parser(
        "eval", help="run the ladder, persist results and write the leaderboard"
    )
    eval_cmd.add_argument(
        "--only",
        nargs="+",
        choices=list(CONFIGS_BY_NAME),
        help="run only these configurations",
    )
    eval_cmd.add_argument(
        "--runs",
        type=int,
        default=1,
        help="repeat each configuration N times and report the spread",
    )
    eval_cmd.add_argument(
        "--models",
        nargs="+",
        help="run the ladder once per model, to separate defence from capability",
    )

    chat_cmd = sub.add_parser("chat", help="interactive session against the guard")
    chat_cmd.add_argument(
        "--config",
        default="full stack",
        choices=list(CONFIGS_BY_NAME),
        help="which guard configuration to run behind the agent",
    )
    chat_cmd.add_argument("--model", help="override the chat model")

    args = parser.parse_args()
    if args.command == "demo":
        asyncio.run(demo(args.only, args.model))
    elif args.command == "eval":
        asyncio.run(evaluate_cmd(args.only, args.models, args.runs))
    elif args.command == "chat":
        asyncio.run(chat(args.config, args.model))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
