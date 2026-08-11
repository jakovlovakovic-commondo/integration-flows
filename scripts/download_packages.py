"""Download one or more Integration Packages from CPI and extract them into git.

Usage:
    python3 scripts/download_packages.py "PackageA,PackageB"

For each package it:
  1. downloads the package content as a ZIP  (…/IntegrationPackages('id')/$value)
  2. extracts it into packages/<PackageId>/
  3. records the active version of every iflow in packages/<PackageId>/.cpi-meta.json
     so the dashboard can later tell whether git is still in sync with CPI.
"""

import io
import os
import sys
import json
import shutil
import zipfile
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpi  # noqa: E402


def download_zip(pkg_id, auth):
    path = f"/api/v1/IntegrationPackages('{pkg_id}')/$value"
    return cpi.api_get(path, auth, accept="application/zip", raw=True)


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("::error::No package IDs given. Pass a comma-separated list as the first argument.", file=sys.stderr)
        sys.exit(1)

    ids = [x.strip() for x in sys.argv[1].split(",") if x.strip()]
    auth = cpi.get_auth_header()

    for pkg_id in ids:
        print(f"→ downloading {pkg_id}")
        zip_bytes = download_zip(pkg_id, auth)

        dest = os.path.join("packages", pkg_id)
        if os.path.isdir(dest):
            shutil.rmtree(dest)
        os.makedirs(dest, exist_ok=True)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            archive.extractall(dest)

        artifacts = cpi.list_artifacts(pkg_id, auth)
        meta = {
            "packageId": pkg_id,
            "syncedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "artifacts": [
                {"id": aid, "name": info["name"], "version": info["version"]}
                for aid, info in sorted(artifacts.items())
            ],
        }
        with open(os.path.join(dest, ".cpi-meta.json"), "w") as handle:
            json.dump(meta, handle, indent=2)

        print(f"  extracted {len(artifacts)} artifact(s)")


if __name__ == "__main__":
    main()
