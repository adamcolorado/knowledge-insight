#!/usr/bin/env python3
"""
Build the site and serve it locally.

    py -3 tools/serve.py                 build, serve on 8000, open a browser
    py -3 tools/serve.py --port 8080     use a different port
    py -3 tools/serve.py --no-build      serve what is already generated
    py -3 tools/serve.py --no-open       do not launch a browser

A plain `py -3 -m http.server` works just as well. This adds three things:
it rebuilds first, it opens the browser only once the socket is actually
listening, and it steps to the next free port if the one you asked for is busy.
"""

import argparse
import subprocess
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_PORT_TRIES = 20


class Server(ThreadingHTTPServer):
    """A server that refuses a port already in use.

    ThreadingHTTPServer sets allow_reuse_address, which on Windows means
    SO_REUSEADDR lets a second process bind a port another process is already
    listening on. Both then appear to start, and requests go to whichever the
    OS picks. Turning it off makes the bind fail honestly so the caller can
    step to the next port.
    """

    allow_reuse_address = False
    daemon_threads = True


class Handler(SimpleHTTPRequestHandler):
    """Serve the repo root, quietly, and without caching during development."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_request(self, code="-", size="-"):
        # Successful requests are noise; failures are worth seeing.
        if isinstance(code, int) and code >= 400:
            sys.stderr.write("  %d  %s\n" % (code, self.requestline))

    def log_error(self, *args):
        pass  # log_request already reports the status once


def build():
    print("Building...", flush=True)
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py")])
    if result.returncode != 0:
        print("\nBuild failed. Fix the errors above and try again.")
        return False
    return True


def listen(port):
    """Bind the first free port at or above the requested one."""
    handler = partial(Handler, directory=str(ROOT))
    for candidate in range(port, port + MAX_PORT_TRIES):
        try:
            return Server(("127.0.0.1", candidate), handler), candidate
        except OSError:
            print("  port %d is busy, trying %d" % (candidate, candidate + 1), flush=True)
    raise SystemExit("No free port between %d and %d." % (port, port + MAX_PORT_TRIES))


def main():
    ap = argparse.ArgumentParser(description="Build and serve Knowledge InSight locally.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    if not args.no_build and not build():
        return 1

    server, port = listen(args.port)
    url = "http://localhost:%d/" % port

    print("\n  Knowledge InSight is running at %s" % url)
    print("  Press Ctrl+C to stop.\n", flush=True)

    # The socket is already bound here, so the browser cannot beat the server.
    if not args.no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
