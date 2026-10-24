"""Command line entry point.

python -m pipeline fetch [--refresh] [--refresh-weather]   download raw public data
python -m pipeline run                                      build features, backtest, forecast
python -m pipeline all [--refresh-weather]                  fetch + run
python -m pipeline report                                   rebuild docs/MODEL_CARD.md from results
"""

from __future__ import annotations

import argparse
import logging
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pipeline", description="KrushiMitra AI data pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("fetch", "all"):
        p = sub.add_parser(name)
        p.add_argument("--refresh", action="store_true", help="re-download every source")
        p.add_argument("--refresh-weather", action="store_true", help="re-download weather only (for new forecasts)")
    sub.add_parser("run")
    sub.add_parser("report")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    from . import fetch, report, train

    if args.command == "report":
        report.write()
        print("wrote docs/MODEL_CARD.md")
        return 0
    if args.command in ("fetch", "all"):
        fetch.fetch_apy(args.refresh)
        fetch.fetch_boundaries(args.refresh)
        fetch.fetch_ibtracs(args.refresh or args.refresh_weather)
        fetch.fetch_power(args.refresh or args.refresh_weather)
    if args.command in ("run", "all"):
        evaluation = train.run()
        chosen = evaluation["chosen"]
        print(f"\nDeployed system: {chosen['key']} (pool: {', '.join(chosen['pool'])})")
        for lead, s in chosen["test_by_lead"].items():
            cov, st = chosen["coverage"][lead], chosen["state_test_by_lead"][lead]
            print(
                f"  {lead}: district RMSE {s['rmse']:.3f} t/ha (skill {s['skill_vs_trend']:+.2f}) | "
                f"state RMSE {st['rmse']:.3f} (skill {st['skill_vs_trend']:+.2f}) | "
                f"80% PI coverage {cov['80']['coverage']:.2f} | now using {chosen['current_choice'][lead]}"
            )
        fixed = chosen["fixed_split_protocol"]
        print(
            f"  (fixed-split protocol would have chosen {fixed['would_have_chosen']}: "
            f"test RMSE {fixed['test_rmse_mean']:.3f})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
