"""
Balaji FeeHub - production static file server for the compiled React app.

Why this exists (do not replace with `python -m http.server`):
-----------------------------------------------------------------------
Python's stdlib http.server sends NO Cache-Control / Expires / ETag
headers at all. Electron's BrowserWindow is a persistent Chromium
session whose HTTP disk cache survives across app restarts AND across
installer/repair/update runs (it lives under
%APPDATA%\\<productName>\\..., completely separate from the
Program-Files install directory the installer manages). Without
explicit cache headers, Chromium applies heuristic caching to
index.html and can keep serving an old, cached copy of the app
indefinitely - even after the real files on disk have been correctly
rebuilt and redeployed. That mismatch was the root cause of clients
authenticating successfully via curl/Postman directly against the
backend, while the Electron shell kept failing login with a stale
bundle silently talking to a stale (or dead) backend URL.

Rules enforced here:
  - "/", "/index.html", and any request with no file extension
    (SPA client-side routes) -> Cache-Control: no-store
    so Chromium ALWAYS revalidates the app shell over the network.
  - Everything under /static/ (CRA's content-hashed JS/CSS/media -
    filenames change automatically whenever content changes) ->
    long-lived immutable caching, which is safe and fast precisely
    BECAUSE the filename itself changes when the content does.
  - Everything else (manifest.json, favicon.ico, robots.txt, images
    directly under public/, etc.) -> short no-cache, must-revalidate,
    since these are not content-hashed and can change between builds.

Usage: python serve_frontend.py <port> <directory>
(same calling convention as `python -m http.server <port> --directory <dir>`)
"""
import sys
import functools
import http.server


def _cache_control_for(path: str) -> str:
    # Anything under the CRA "static/" output directory is content-hashed
    # (e.g. static/js/main.8f3a1c2d.js) - the filename changes whenever the
    # content does, so it is safe to cache aggressively and immutably.
    if "/static/" in path:
        return "public, max-age=31536000, immutable"
    # The app shell (index.html) and any extensionless SPA route must
    # always be revalidated so a rebuilt app is picked up on next launch.
    return "no-store, no-cache, must-revalidate"


class NoStaleCacheHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        try:
            self.send_header("Cache-Control", _cache_control_for(self.path))
            if _cache_control_for(self.path).startswith("no-store"):
                self.send_header("Pragma", "no-cache")
                self.send_header("Expires", "0")
        except Exception:
            pass
        super().end_headers()

    # Quieter logging (NSSM captures stdout/stderr to AppStdout/AppStderr
    # log files already configured with rotation).
    def log_message(self, fmt, *args):
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), fmt % args))


def main():
    if len(sys.argv) < 3:
        print("Usage: python serve_frontend.py <port> <directory>", file=sys.stderr)
        sys.exit(2)
    port = int(sys.argv[1])
    directory = sys.argv[2]
    handler = functools.partial(NoStaleCacheHandler, directory=directory)
    with http.server.ThreadingHTTPServer(("0.0.0.0", port), handler) as httpd:
        print(f"Balaji FeeHub frontend server (cache-safe) listening on 0.0.0.0:{port}, serving {directory}")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
