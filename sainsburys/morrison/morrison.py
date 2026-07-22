"""
Morrison — the fridge guardian desktop pet.

Floats in the bottom-right corner of the screen whenever the fridge has
leftovers (checked against the local lunch.db every 60s). Click him to post a
fresh rescue board to the demo channel and jump straight there in Slack.

    pip install pyobjc-framework-Cocoa    # one-off (macOS only)
    python morrison/morrison.py            # only appears if leftovers exist
    MORRISON_ALWAYS=1 python morrison/morrison.py   # force-show (testing)
    MORRISON_POLL=5 python morrison/morrison.py     # demo: 5s mood updates

Moods: happy bounce while leftovers exist; sad (tears + broken-heart burger)
when anything expires today; hidden when the fridge is clear. Frames live in
morrison/frames/ and morrison/frames-sad/ — swap art, no code changes.
"""
import os
import sys
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent                      # sainsburys/
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import store  # safe: only needs the SQLite file, no tokens

from AppKit import (NSApplication, NSApplicationActivationPolicyAccessory,
                    NSBackingStoreBuffered, NSColor, NSFloatingWindowLevel,
                    NSImage, NSImageView, NSMakeRect, NSScreen, NSURL,
                    NSWindow, NSWindowStyleMaskBorderless, NSWorkspace)
from Foundation import NSObject, NSTimer
from PyObjCTools import AppHelper

TEAM_ID = os.environ.get("MORRISON_TEAM_ID", "T02JSEVKLDT")
CHANNEL_ID = os.environ.get("MORRISON_CHANNEL_ID", "C0BK4D24LS0")
DEEPLINK = "slack://channel?team=%s&id=%s" % (TEAM_ID, CHANNEL_ID)
FRIDAY_ONLY = os.environ.get("MORRISON_FRIDAY_ONLY") == "1"
ALWAYS = os.environ.get("MORRISON_ALWAYS") == "1"
POLL_SECONDS = float(os.environ.get("MORRISON_POLL", "60"))  # demo: MORRISON_POLL=5

W, H = 150, 175
MARGIN = 24


def fridge_mood():
    """
    What the fridge looks like: 'hidden' (nothing to rescue), 'happy'
    (leftovers, none urgent), or 'sad' (something expires today).
    """
    if FRIDAY_ONLY and not ALWAYS:
        from datetime import date
        if date.today().weekday() != 4:
            return "hidden"
    try:
        items = store.leftovers()
    except Exception as e:
        # Say WHY we're hiding — a stale-schema lunch.db lands here.
        print("morrison: fridge check failed (%s: %s) — is lunch.db seeded "
              "with the current schema? Try: python data/seed.py" % (type(e).__name__, e))
        items = []
    if any(i["days_left"] <= 0 for i in items):
        return "sad"
    if items:
        return "happy"
    return "happy" if ALWAYS else "hidden"


_last_post = [0.0]
POST_COOLDOWN = 300  # one board per 5 min — repeat clicks just open Slack


def post_board_and_open_slack():
    """Post a fresh rescue board (only if there are leftovers, max once per
    cooldown), then open Slack on the demo channel."""
    import time
    try:
        token = os.environ.get("SLACK_BOT_TOKEN")
        if (token and store.leftovers()
                and time.time() - _last_post[0] > POST_COOLDOWN):
            from slack_sdk import WebClient
            from flows import rescue
            rescue.post_board(WebClient(token=token), CHANNEL_ID)
            _last_post[0] = time.time()
    except Exception as e:
        print("morrison: board post failed (%s) — opening Slack anyway" % e)
    NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(DEEPLINK))


class MorrisonView(NSImageView):
    def mouseDown_(self, event):
        threading.Thread(target=post_board_and_open_slack, daemon=True).start()


class Morrison(NSObject):
    def applicationDidFinishLaunching_(self, note):
        def load(folder):
            return [NSImage.alloc().initWithContentsOfFile_(str(p))
                    for p in sorted((HERE / folder).glob("frame_*.png"))]
        self.moods = {"happy": load("frames"), "sad": load("frames-sad")}
        self.frames = self.moods["happy"]
        self.idx = 0

        screen = NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - W - MARGIN
        y = screen.origin.y + MARGIN
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x, y, W, H), NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered, False)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setLevel_(NSFloatingWindowLevel)
        self.window.setCollectionBehavior_(1 << 0)  # canJoinAllSpaces

        self.view = MorrisonView.alloc().initWithFrame_(NSMakeRect(0, 0, W, H))
        self.view.setImage_(self.frames[0])
        self.window.setContentView_(self.view)

        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1 / 30.0, self, "tick:", None, True)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            POLL_SECONDS, self, "checkFridge:", None, True)
        self.checkFridge_(None)

    def tick_(self, timer):
        self.idx = (self.idx + 1) % len(self.frames)
        self.view.setImage_(self.frames[self.idx])

    def checkFridge_(self, timer):
        mood = fridge_mood()
        if mood == "hidden":
            self.window.orderOut_(None)
            return
        if self.moods.get(mood) and self.frames is not self.moods[mood]:
            self.frames = self.moods[mood]
            self.idx = 0
        self.window.orderFrontRegardless()


if __name__ == "__main__":
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no dock icon
    delegate = Morrison.alloc().init()
    app.setDelegate_(delegate)
    print("Morrison is watching the fridge… (Ctrl-C to stop)")
    AppHelper.runEventLoop()
