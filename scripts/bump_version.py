#!/usr/bin/env python3

"""
Bump semantic version in client/package.json.

Usage: 
    python scripts/bump_version.py [major|minor|patch]
"""

import argparse, json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE_JSON = ROOT / "src" / "client" / "package.json"


def read_package_json() -> tuple[str, tuple[int, int, int]]:
    """
    Read package.json and extract the current version.
    
    :return: tuple of file content and version tuple (major, minor, patch)
    """
    # txt = PYPROJECT.read_text(encoding="utf-8")
    # m = re.search(r'(?m)^\s*version\s*=\s*"(\d+)\.(\d+)\.(\d+)"\s*$', txt)
    txt = PACKAGE_JSON.read_text(encoding="utf-8")
    data = json.loads(txt)
    version_str = data.get("version")
    if not version_str:
        raise SystemExit("Could not find version in package.json")
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str)
    if not m:
        raise SystemExit("Could not find version = \"X.Y.Z\" in package.json")
    return txt, tuple(map(int, m.groups()))


def write_package_json(txt: str, new_version: str) -> None:
    """
    Write the new version back to package.json.

    :param txt: original file content
    :param new_version: new version string
    :return: None
    """
    data = json.loads(txt)
    data["version"] = new_version
    PACKAGE_JSON.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def bump(ver: tuple[int, int, int], kind: str) -> str:
    """
    Bump the version based on the kind.

    :param ver: current version tuple (major, minor, patch)
    :param kind: kind of bump ("major", "minor", "patch")
    :return: new version string
    """
    major, minor, patch = ver
    if kind == "major":
        return f"{major + 1}.0.0"
    elif kind == "minor":
        return f"{major}.{minor + 1}.0"
    elif kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        raise SystemExit(f"Kind must be one of major, minor, patch; got {kind!r}")
    

def main() -> None:
    """
    Main function to parse arguments and bump version.
    """
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=["major", "minor", "patch"])
    args = p.parse_args()

    txt, cur = read_package_json()
    new_version = bump(cur, args.kind)
    write_package_json(txt, new_version)
    print(new_version)  # workflow reads new version from stdout for tagging


if __name__ == "__main__":
    main()