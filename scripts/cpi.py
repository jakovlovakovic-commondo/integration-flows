"""Shared helpers for talking to SAP Integration Suite (CPI) OData API.

Uses only the Python standard library — no pip installs needed on the runner.
Authentication: HTTP Basic (technical user).

Required environment variables:
  CPI_API_URL   API base host (service key/tenant "url",
                e.g. https://xxx.it-cpiXXX.cfapps.eu10-002.hana.ondemand.com)
  CPI_USER      Technical user name (needs API read roles
                WorkspacePackagesRead / WorkspaceArtifactsRead)
  CPI_PASSWORD  Technical user password
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error


def _env(name):
    value = os.environ.get(name)
    if not value:
        print(f"::error::Missing environment variable {name}", file=sys.stderr)
        sys.exit(1)
    return value.strip()


def get_auth_header():
    """Build an HTTP Basic auth header and mask the encoded blob in the logs."""
    user = _env("CPI_USER")
    password = _env("CPI_PASSWORD")
    blob = base64.b64encode(f"{user}:{password}".encode()).decode()
    print(f"::add-mask::{blob}")
    return f"Basic {blob}"


def api_base():
    return _env("CPI_API_URL").rstrip("/")


def api_get(path, auth, accept="application/json", raw=False):
    """GET an OData path. Returns parsed JSON, or raw bytes when raw=True."""
    url = api_base() + path
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", auth)
    req.add_header("Accept", accept)

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        print(f"::error::GET {path} failed ({exc.code}): {detail}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"::error::GET {path} failed: {exc.reason}", file=sys.stderr)
        sys.exit(1)

    if raw:
        return data
    return json.loads(data.decode())


def list_artifacts(pkg_id, auth):
    """Return {artifactId: {'name': ..., 'version': ...}} for a package's iflows."""
    path = f"/api/v1/IntegrationPackages('{pkg_id}')/IntegrationDesigntimeArtifacts"
    data = api_get(path, auth)
    results = data.get("d", {}).get("results", [])
    out = {}
    for art in results:
        art_id = art.get("Id")
        if not art_id:
            continue
        out[art_id] = {
            "name": art.get("Name") or art_id,
            "version": art.get("Version"),
        }
    return out
