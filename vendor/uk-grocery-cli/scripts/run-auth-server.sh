#!/bin/sh
# Wraps the auth-server so login.ts's headless:false browser has somewhere to
# render. On a laptop (real display, no xvfb-run installed) this just falls
# through to running it directly — the same script works in both places.
if command -v xvfb-run >/dev/null 2>&1; then
    exec xvfb-run -a --server-args='-screen 0 1280x800x24' npm run auth-server
else
    exec npm run auth-server
fi
