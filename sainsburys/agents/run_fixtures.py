"""
Poor man's evals — run all fixtures through each agent and print results.
Run after every prompt change: python agents/run_fixtures.py
"""
import json
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def run_parser_fixtures():
    from agents.parser import parse
    print("=== Parser fixtures ===")
    for f in sorted(FIXTURES_DIR.glob("parser_*.json")):
        fixture = json.loads(f.read_text())
        print(f"\n-- {f.name} --")
        print(f"Input: {fixture['freeform']}")
        result = parse(fixture["user_slack_id"], fixture["freeform"], fixture["half"])
        print(f"Output: {json.dumps(result, indent=2)}")


def run_suggester_fixtures():
    from agents.suggester import suggest
    print("\n=== Suggester fixtures ===")
    for f in sorted(FIXTURES_DIR.glob("suggester_*.json")):
        fixture = json.loads(f.read_text())
        print(f"\n-- {f.name} --")
        result = suggest(fixture["user_slack_ids"], fixture.get("last_two_weeks", []))
        print(f"Output: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    run_parser_fixtures()
    run_suggester_fixtures()
