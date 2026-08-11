"""Compare what is committed in git against what is live in CPI.

For every package that has been downloaded (i.e. has packages/<id>/.cpi-meta.json),
this reads the recorded iflow versions and compares them against the current active
versions in CPI, then writes docs/dashboard-data.json for the dashboard generator.

Status per artifact:
  up-to-date       git version == CPI version
  outdated         versions differ (someone changed the iflow in CPI since last sync)
  missing-in-git   exists in CPI but not in the git snapshot (never downloaded)
  deleted-in-cpi   in the git snapshot but no longer in CPI
"""

import os
import sys
import glob
import json
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cpi  # noqa: E402


def package_info(pkg_id, auth):
    data = cpi.api_get(f"/api/v1/IntegrationPackages('{pkg_id}')", auth)
    d = data.get("d", {})
    return {"version": d.get("Version"), "modifiedDate": d.get("ModifiedDate")}


def classify(git_version, cpi_version):
    if git_version == cpi_version:
        return "up-to-date"
    if git_version is None:
        return "missing-in-git"
    if cpi_version is None:
        return "deleted-in-cpi"
    return "outdated"


def main():
    auth = cpi.get_auth_header()

    packages = []
    all_up_to_date = True

    meta_files = sorted(glob.glob(os.path.join("packages", "*", ".cpi-meta.json")))
    if not meta_files:
        print("::warning::No packages/*/.cpi-meta.json found. Run the download workflow first.")

    for meta_path in meta_files:
        with open(meta_path) as handle:
            meta = json.load(handle)

        pkg_id = meta["packageId"]
        git_arts = {a["id"]: a for a in meta.get("artifacts", [])}
        live_arts = cpi.list_artifacts(pkg_id, auth)
        info = package_info(pkg_id, auth)

        artifacts = []
        pkg_up_to_date = True
        for art_id in sorted(set(git_arts) | set(live_arts)):
            git_v = git_arts.get(art_id, {}).get("version")
            live = live_arts.get(art_id)
            cpi_v = live["version"] if live else None
            name = (live or git_arts.get(art_id) or {}).get("name", art_id)
            status = classify(git_v, cpi_v)
            if status != "up-to-date":
                pkg_up_to_date = False
                all_up_to_date = False
            artifacts.append({
                "id": art_id,
                "name": name,
                "gitVersion": git_v,
                "cpiVersion": cpi_v,
                "status": status,
            })

        packages.append({
            "packageId": pkg_id,
            "syncedAt": meta.get("syncedAt"),
            "cpiPackageVersion": info["version"],
            "cpiModifiedDate": info["modifiedDate"],
            "upToDate": pkg_up_to_date,
            "artifacts": artifacts,
        })

    report = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "allUpToDate": all_up_to_date,
        "packageCount": len(packages),
        "packages": packages,
    }

    os.makedirs("docs", exist_ok=True)
    with open(os.path.join("docs", "dashboard-data.json"), "w") as handle:
        json.dump(report, handle, indent=2)

    print(f"Checked {len(packages)} package(s); all up to date: {all_up_to_date}")


if __name__ == "__main__":
    main()
