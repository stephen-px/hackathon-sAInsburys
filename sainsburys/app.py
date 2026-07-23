import atexit
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from slack_surface import handlers

REQUIRED_ENV = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "ANTHROPIC_API_KEY"]

# vendor/uk-grocery-cli's auth-server backs /authenticate (see grocery.py's
# AUTH_SERVER). It's spawned here so running the bot is still just `python
# app.py` — no second terminal to start it in.
AUTH_SERVER_DIR = Path(__file__).parent.parent / "vendor" / "uk-grocery-cli"


def _check_env():
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing env vars: {', '.join(missing)} — copy .env.example to .env and fill them in.")


def _start_auth_server():
    """Best-effort: /authenticate just won't work if this fails, everything else still does."""
    if not AUTH_SERVER_DIR.exists():
        print("⚠️  vendor/uk-grocery-cli not found — /authenticate will be unavailable.", flush=True)
        return None
    try:
        # Inherit stdout/stderr (no DEVNULL) — if npm/node/tsx is missing or the
        # port's taken, the reason lands right here instead of as a silent
        # "connection refused" the next time someone runs /authenticate.
        # run-auth-server.sh wraps with xvfb-run when it's available (inside
        # the Docker `bot` container) and runs directly otherwise (a laptop's
        # real display) — same command works in both places.
        script = AUTH_SERVER_DIR / "scripts" / "run-auth-server.sh"
        proc = subprocess.Popen(["sh", str(script)], cwd=str(AUTH_SERVER_DIR))
    except OSError as e:
        print("⚠️  couldn't start the Sainsbury's auth-server (%s) — /authenticate will be unavailable." % e, flush=True)
        return None
    atexit.register(proc.terminate)
    print("🔐 Sainsbury's auth-server starting (pid %d) — /authenticate will be ready in a few seconds." % proc.pid, flush=True)
    return proc


def main():
    _check_env()
    _start_auth_server()
    app = App(token=os.environ["SLACK_BOT_TOKEN"])
    handlers.register(app)
    # Heal historical events recorded before names were captured — the
    # dashboard shows raw U… IDs for anyone missing from `users`.
    import identity
    identity.backfill_missing_names(app.client)
    print("⚡ sAInsburys connecting via Socket Mode…")
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()


if __name__ == "__main__":
    main()
