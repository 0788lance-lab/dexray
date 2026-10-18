"""Data-quality checks: verify parsed swaps against raw on-chain balance changes.

Two parts:

- ``raw_changes`` / ``looks_like_swap`` / ``verify_swap`` -- an oracle that
  recomputes what a swap must look like straight from integer pre/post
  balances. It is deliberately written independently of ``parse_swap`` so a
  parser regression shows up as a disagreement instead of being copied.
- ``run_check`` -- samples recent mainnet transactions per DEX program, parses
  them, and scores the parser against the oracle. A DEX upgrade that makes the
  parser silently wrong shows up as a falling success rate.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import requests

from dexray.core import Swap
from dexray.solana.parser import DEX_PROGRAMS, SOL_DUST, TOKEN_DUST, WSOL, parse_swap
from dexray.solana.rpc import MultiRPC

log = logging.getLogger("dexray.quality")

SOL_DUST_LAMPORTS = int(SOL_DUST * 10**9)
DEFAULT_THRESHOLD = 0.98
MIN_SWAPS = 10          # fewer scored swaps than this -> low-sample warning


# ---------------------------------------------------------------------------
# oracle
# ---------------------------------------------------------------------------

def _keys(tx: dict) -> list[str]:
    keys = tx.get("transaction", {}).get("message", {}).get("accountKeys", [])
    return [k["pubkey"] if isinstance(k, dict) else k for k in keys]


def _signers(tx: dict) -> list[str]:
    message = tx.get("transaction", {}).get("message", {})
    keys = message.get("accountKeys", [])
    if keys and isinstance(keys[0], dict):
        return [k["pubkey"] for k in keys if k.get("signer")]
    n = message.get("header", {}).get("numRequiredSignatures", 1)
    return _keys(tx)[:n]


def raw_changes(tx: dict, owner: str) -> dict[str, tuple[int, int]]:
    """Integer balance change per mint for ``owner``: {mint: (raw_delta, decimals)}.

    Native SOL and WSOL are merged under the WSOL mint (9 decimals), with the
    network fee added back when ``owner`` paid it.
    """
    meta = tx.get("meta") or {}
    changes: dict[str, list[int]] = {}
    for side, sign in (("preTokenBalances", -1), ("postTokenBalances", 1)):
        for entry in meta.get(side) or []:
            if entry.get("owner") != owner:
                continue
            ui = entry.get("uiTokenAmount", {})
            slot = changes.setdefault(entry["mint"], [0, int(ui.get("decimals", 0))])
            slot[0] += sign * int(ui.get("amount", "0"))

    keys = _keys(tx)
    if owner in keys:
        i = keys.index(owner)
        pre, post = meta.get("preBalances", []), meta.get("postBalances", [])
        if i < len(pre) and i < len(post):
            lamports = post[i] - pre[i] + (meta.get("fee", 0) if i == 0 else 0)
            slot = changes.setdefault(WSOL, [0, 9])
            slot[0] += lamports

    return {m: (d, dec) for m, (d, dec) in changes.items() if d != 0}


def _legs(changes: dict[str, tuple[int, int]]) -> tuple[list[str], list[str]]:
    """Mints that went in / out, ignoring SOL dust and routing dust."""
    ins, outs = [], []
    for mint, (delta, decimals) in changes.items():
        if mint == WSOL and abs(delta) < SOL_DUST_LAMPORTS:
            continue
        if mint != WSOL and abs(delta) < TOKEN_DUST * 10 ** decimals:
            continue
        (ins if delta > 0 else outs).append(mint)
    return ins, outs


def swapping_signers(tx: dict) -> list[str]:
    """Signers that swapped: exactly one asset in and one out.

    Usually one; bundles (e.g. volume bots) can hold a swap per signer.
    """
    meta = tx.get("meta")
    if not meta or meta.get("err") is not None:
        return []
    swappers = []
    for signer in _signers(tx):
        ins, outs = _legs(raw_changes(tx, signer))
        if len(ins) == 1 and len(outs) == 1:
            swappers.append(signer)
    return swappers


def looks_like_swap(tx: dict) -> str | None:
    """Return the first signer that swapped, else None."""
    swappers = swapping_signers(tx)
    return swappers[0] if swappers else None


def _human(raw: int, decimals: int) -> float:
    return abs(raw) / 10 ** decimals


def _same(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-9 * max(1.0, abs(b))


def verify_swap(tx: dict, swap: Swap) -> list[str]:
    """Check a parsed swap against raw balances. Returns problems ([] = consistent)."""
    problems: list[str] = []
    keys = _keys(tx)
    if keys and swap.fee_payer != keys[0]:
        problems.append(f"fee_payer {swap.fee_payer} != accountKeys[0] {keys[0]}")
    if swap.trader not in _signers(tx):
        problems.append(f"trader {swap.trader} did not sign the tx")

    changes = raw_changes(tx, swap.trader)
    token_sign = 1 if swap.direction == "BUY" else -1

    token = changes.get(swap.mint)
    if token is None:
        problems.append(f"token {swap.mint} balance did not change")
    else:
        if token[0] * token_sign <= 0:
            problems.append(f"direction {swap.direction} but token delta is {token[0]}")
        if not _same(swap.token_amount, _human(*token)):
            problems.append(f"token_amount {swap.token_amount} != chain {_human(*token)}")

    quote = changes.get(swap.quote_mint)
    if quote is None:
        problems.append(f"quote {swap.quote_mint} balance did not change")
    else:
        if quote[0] * token_sign >= 0:
            problems.append(f"direction {swap.direction} but quote delta is {quote[0]}")
        if not _same(swap.quote_amount, _human(*quote)):
            problems.append(f"quote_amount {swap.quote_amount} != chain {_human(*quote)}")
    return problems


# ---------------------------------------------------------------------------
# sampling run
# ---------------------------------------------------------------------------

@dataclass
class DexResult:
    source: str
    program: str
    signatures: int = 0                   # recent successful txs found for the program
    sampled: int = 0
    unavailable: int = 0                  # transient fetch failures (429, timeouts)
    rpc_errors: list[dict] = field(default_factory=list)   # RPC refused the tx
    exceptions: list[dict] = field(default_factory=list)   # parse_swap raised
    swaps: int = 0                        # oracle says it's a swap
    parsed_ok: int = 0                    # parsed and verified
    missed: list[dict] = field(default_factory=list)       # swap, parser returned None
    wrong: list[dict] = field(default_factory=list)        # parsed, but verify failed
    spurious: list[dict] = field(default_factory=list)     # parsed a non-swap
    examples: list[str] = field(default_factory=list)      # sigs for manual review

    @property
    def scored(self) -> int:
        return self.swaps + len(self.rpc_errors) + len(self.exceptions)

    @property
    def success_rate(self) -> float | None:
        return self.parsed_ok / self.scored if self.scored else None

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "program": self.program,
            "signatures": self.signatures,
            "sampled": self.sampled,
            "unavailable": self.unavailable,
            "swaps": self.swaps,
            "parsed_ok": self.parsed_ok,
            "success_rate": self.success_rate,
            "rpc_errors": self.rpc_errors,
            "exceptions": self.exceptions,
            "missed": self.missed,
            "wrong": self.wrong,
            "spurious": self.spurious,
            "examples": self.examples,
        }


def _sample_signatures(rpc: MultiRPC, program: str) -> list[str]:
    """The program's last 1000 successful signatures, in a fixed shuffled order
    so a burst from one bot doesn't dominate the sample."""
    infos = rpc.get_signatures(program, limit=1000)
    sigs = [i["signature"] for i in infos if i.get("err") is None]
    random.Random(0).shuffle(sigs)
    return sigs


def _fetch(rpc: MultiRPC, sig: str) -> tuple[dict | None, str | None, bool]:
    """Returns (tx, error, transient)."""
    try:
        tx = rpc.get_transaction(sig)
    except ConnectionError as e:
        cause = e.__cause__
        # MultiRPC raises RuntimeError for JSON-RPC error responses: the node
        # answered and refused (e.g. -32015 unsupported tx version).
        if isinstance(cause, RuntimeError):
            return None, str(cause)[:300], False
        return None, f"{type(cause).__name__}: {cause}"[:300], True
    if tx is None:
        return None, "not found", True
    return tx, None, False


def check_dex(
    rpc: MultiRPC,
    program: str,
    source: str,
    per_dex: int = 50,
    parse_fn: Callable[[dict], Swap | None] = parse_swap,
    n_examples: int = 5,
    max_fetch: int | None = None,
) -> DexResult:
    """Fetch txs until ``per_dex`` swaps are scored or ``max_fetch`` (default
    4 x per_dex) txs were fetched; many program txs are bots, not user swaps."""
    max_fetch = max_fetch or per_dex * 4
    res = DexResult(source=source, program=program)
    sigs = _sample_signatures(rpc, program)
    res.signatures = len(sigs)
    for sig in sigs:
        if res.scored >= per_dex or res.sampled >= max_fetch:
            break
        res.sampled += 1
        tx, err, transient = _fetch(rpc, sig)
        if tx is None:
            if transient:
                res.unavailable += 1
            else:
                res.rpc_errors.append({"sig": sig, "error": err})
            continue

        try:
            swap = parse_fn(tx)
        except Exception as e:  # noqa: BLE001 -- any raise is a parser bug
            res.exceptions.append({"sig": sig, "error": f"{type(e).__name__}: {e}"[:300]})
            continue

        swappers = swapping_signers(tx)
        if not swappers:
            # A SOL leg below dust is indistinguishable from rent (tiny buy vs
            # airdrop + new ATA), so only flag parses the oracle clearly rejects.
            tiny_sol = swap is not None and swap.quote_mint == WSOL \
                and swap.quote_amount * 1e9 < SOL_DUST_LAMPORTS
            if swap is not None and not tiny_sol:
                res.spurious.append({"sig": sig, "swap": swap.to_dict()})
            continue

        res.swaps += 1
        if swap is None:
            res.missed.append({"sig": sig, "trader": swappers[0]})
            continue
        problems = verify_swap(tx, swap)
        if swap.trader not in swappers:
            problems.append(f"trader {swap.trader} is not a swapping signer {swappers}")
        if problems:
            res.wrong.append({"sig": sig, "problems": problems})
        else:
            res.parsed_ok += 1
            if len(res.examples) < n_examples:
                res.examples.append(sig)
    return res


def run_check(
    rpc: MultiRPC,
    per_dex: int = 50,
    programs: dict[str, str] | None = None,
    parse_fn: Callable[[dict], Swap | None] = parse_swap,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """Sample each DEX program and score the parser. Returns a JSON-able report."""
    programs = programs or DEX_PROGRAMS
    results = []
    for program, source in programs.items():
        log.info("checking %s (%s)", source, program)
        try:
            results.append(check_dex(rpc, program, source, per_dex, parse_fn))
        except ConnectionError as e:
            log.error("could not sample %s: %s", source, e.__cause__ or e)
            results.append(DexResult(source=source, program=program))

    alerts, warnings = [], []
    for r in results:
        rate = r.success_rate
        if r.signatures == 0:
            alerts.append(f"{r.source}: no recent transactions for {r.program} "
                          "(wrong program ID, program migrated, or sampling failed)")
        elif rate is not None and rate < threshold:
            alerts.append(f"{r.source}: success rate {rate:.1%} < {threshold:.0%} "
                          f"(missed {len(r.missed)}, wrong {len(r.wrong)}, "
                          f"rpc errors {len(r.rpc_errors)}, exceptions {len(r.exceptions)})")
        elif r.wrong or r.exceptions:
            # Silent miscalculation is the worst failure; one verified case is
            # enough, even when the rate still rounds to the threshold.
            alerts.append(f"{r.source}: {len(r.wrong)} wrong parse(s), "
                          f"{len(r.exceptions)} exception(s) at {rate:.1%}")
        if r.signatures and r.scored < MIN_SWAPS:
            warnings.append(f"{r.source}: low sample, {r.scored} swaps in {r.sampled} txs "
                            f"({r.unavailable} unavailable); most program traffic is not user swaps")
    return {
        "time": int(time.time()),
        "per_dex": per_dex,
        "threshold": threshold,
        "alerts": alerts,
        "warnings": warnings,
        "dexes": [r.to_dict() for r in results],
    }


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def save_report(report: dict, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d-%H%M%S", time.gmtime(report["time"]))
    path = out / f"quality-{stamp}.json"
    path.write_text(json.dumps(report, indent=2))
    (out / f"quality-{stamp}.md").write_text(render_markdown(report, load_history(out)))
    return path


def load_history(out_dir: str | Path, limit: int = 8) -> list[dict]:
    """Most recent saved reports, oldest first."""
    paths = sorted(Path(out_dir).glob("quality-*.json"))[-limit:]
    return [json.loads(p.read_text()) for p in paths]


def _pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate:.1%}"


def render_markdown(report: dict, history: list[dict] | None = None) -> str:
    history = [h for h in history or [] if h["time"] != report["time"]] + [report]
    dates = [time.strftime("%m-%d", time.gmtime(h["time"])) for h in history]
    lines = [
        f"# DexRay quality report {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(report['time']))}",
        "",
        f"Threshold {report['threshold']:.0%}, target {report['per_dex']} swaps per DEX.",
        "",
    ]
    if report["alerts"]:
        lines += ["## ALERTS", ""] + [f"- {a}" for a in report["alerts"]] + [""]
    else:
        lines += ["All DEXes at or above threshold.", ""]
    if report.get("warnings"):
        lines += ["## Warnings", ""] + [f"- {w}" for w in report["warnings"]] + [""]

    lines += [
        "| DEX | sampled | swaps | ok | missed | wrong | rpc err | exc | spurious | rate |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for d in report["dexes"]:
        lines.append(
            f"| {d['source']} | {d['sampled']} | {d['swaps']} | {d['parsed_ok']} | "
            f"{len(d['missed'])} | {len(d['wrong'])} | {len(d['rpc_errors'])} | "
            f"{len(d['exceptions'])} | {len(d['spurious'])} | {_pct(d['success_rate'])} |"
        )

    lines += ["", "## Trend", "", "| DEX | " + " | ".join(dates) + " |",
              "|---|" + "---|" * len(dates)]
    for d in report["dexes"]:
        row = []
        for h in history:
            past = next((x for x in h["dexes"] if x["source"] == d["source"]), None)
            row.append(_pct(past["success_rate"]) if past else "-")
        lines.append(f"| {d['source']} | " + " | ".join(row) + " |")

    lines += ["", "## Problems", ""]
    any_problem = False
    for d in report["dexes"]:
        for kind in ("rpc_errors", "exceptions", "missed", "wrong", "spurious"):
            for item in d[kind][:5]:
                any_problem = True
                detail = item.get("error") or item.get("problems") or item.get("swap") or item.get("trader")
                lines.append(f"- {d['source']} {kind}: `{item['sig']}` {detail}")
    if not any_problem:
        lines.append("None.")

    lines += ["", "## Spot-check samples", ""]
    for d in report["dexes"]:
        for sig in d["examples"]:
            lines.append(f"- {d['source']}: https://solscan.io/tx/{sig}")
    return "\n".join(lines) + "\n"


def notify(report: dict) -> None:
    """Send alerts to Telegram / Slack when configured via env vars."""
    if not report["alerts"]:
        return
    text = "DexRay quality alert\n" + "\n".join(f"- {a}" for a in report["alerts"])
    token, chat = os.environ.get("DEXRAY_TELEGRAM_BOT_TOKEN"), os.environ.get("DEXRAY_TELEGRAM_CHAT_ID")
    if token and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": text}, timeout=15)
        except requests.RequestException as e:
            log.error("telegram notify failed: %s", e)
    webhook = os.environ.get("DEXRAY_SLACK_WEBHOOK")
    if webhook:
        try:
            requests.post(webhook, json={"text": text}, timeout=15)
        except requests.RequestException as e:
            log.error("slack notify failed: %s", e)
