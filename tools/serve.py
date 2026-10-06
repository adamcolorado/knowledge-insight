#!/usr/bin/env python3
"""
Build the site and serve it locally.

    py -3 tools/serve.py                 build, serve on 8000, open a browser
    py -3 tools/serve.py --lan           also serve to phones on the same Wi-Fi
    py -3 tools/serve.py --port 8080     use a different port
    py -3 tools/serve.py --no-build      serve what is already generated
    py -3 tools/serve.py --no-open       do not launch a browser

A plain `py -3 -m http.server` works just as well. This adds three things:
it rebuilds first, it opens the browser only once the socket is actually
listening, and it steps to the next free port if the one you asked for is busy.
"""

import argparse
import socket
import subprocess
import sys
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs"
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
    """Serve docs/, quietly, and without caching during development.

    /tools/ is mapped to the repo's tools/ folder so the overflow probe still
    loads locally, though it is never published.
    """

    def translate_path(self, path):
        if path.startswith("/tools/"):
            tools = ROOT / "tools"
            name = unquote(path[len("/tools/"):].split("?", 1)[0].split("#", 1)[0])
            target = (tools / name).resolve()
            if target.parent == tools:
                return str(target)
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_request(self, code="-", size="-"):
        # Successful requests are noise; failures are worth seeing.
        if isinstance(code, int) and code >= 400:
            sys.stderr.write("  %d  %s\n" % (code, self.requestline))

    def log_error(self, *args):
        pass  # log_request already reports the status once


def lan_addresses():
    """This machine's addresses on the local network.

    The UDP connect sends no packets; it just asks the routing table which
    interface would be used to reach the internet, which is the address a phone
    on the same Wi-Fi should use.
    """
    found = set()
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        found.add(probe.getsockname()[0])
    except OSError:
        pass
    finally:
        probe.close()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if not address.startswith("127.") and not address.startswith("169.254."):
                found.add(address)
    except OSError:
        pass
    return sorted(found)


def build():
    print("Building...", flush=True)
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "build.py")])
    if result.returncode != 0:
        print("\nBuild failed. Fix the errors above and try again.")
        return False
    return True


def listen(port, host="127.0.0.1"):
    """Bind the first free port at or above the requested one."""
    handler = partial(Handler, directory=str(SITE))
    for candidate in range(port, port + MAX_PORT_TRIES):
        try:
            return Server((host, candidate), handler), candidate
        except OSError:
            print("  port %d is busy, trying %d" % (candidate, candidate + 1), flush=True)
    raise SystemExit("No free port between %d and %d." % (port, port + MAX_PORT_TRIES))


def main():
    ap = argparse.ArgumentParser(description="Build and serve Knowledge InSight locally.")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--lan", action="store_true",
                    help="serve to other devices on this network (phones, tablets)")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()

    if not args.no_build and not build():
        return 1

    # Binding every interface is opt-in: it exposes the site to the network.
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    server, port = listen(args.port, host)
    url = "http://localhost:%d/" % port

    print("\n  Knowledge InSight is running at %s" % url)
    if args.lan:
        addresses = lan_addresses()
        if addresses:
            print("\n  On this network, open any of these on your phone:")
            for address in addresses:
                print("      http://%s:%d/" % (address, port))
            print("\n  Same Wi-Fi required. If the phone cannot connect, Windows")
            print("  Firewall is blocking the port -- see README, 'Testing on a phone'.")
        else:
            print("\n  No network address found; is Wi-Fi connected?")
    print("\n  Press Ctrl+C to stop.\n", flush=True)

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
