#!/usr/bin/env python3
"""Seeds demo users (one per role), organizations, memberships and the downloaded corpus through the real HTTP API.

    ./scripts/fetch_corpus.sh && python scripts/seed_demo.py [--base http://localhost:8080] [--limit N]

Idempotent: existing users/orgs/documents (same filename) are reused/skipped. Local demo only: the password is public.
"""

import argparse
import sys
import time
from pathlib import Path

import requests

PASSWORD = "Demo-Pass-2026!"
CORPUS = Path(__file__).resolve().parent.parent / "data" / "corpus"

# org name -> (corpus dir, {email: role})
ORGS = {
    "Acme Engineering": ("acme-engineering", {"owner@acme.test": "owner", "admin@acme.test": "admin", "member@acme.test": "member", "multi@demo.test": "member"}),
    "Globex Library": ("globex-library", {"owner@globex.test": "owner", "admin@acme.test": "admin", "multi@demo.test": "admin"}),
    "Oʻzbek Bilim Bazasi": ("uzbek-bilim-bazasi", {"owner@uz.test": "owner", "admin@acme.test": "member", "multi@demo.test": "admin"}),
    "Initech Docs": ("initech-docs", {"multi@demo.test": "owner", "member@acme.test": "member"}),
}
USERS = {
    "owner@acme.test": "Olivia Owner",
    "admin@acme.test": "Adam Admin",
    "member@acme.test": "Mia Member",
    "owner@globex.test": "Greg Globex",
    "multi@demo.test": "Max Multi-Org",
    "outsider@demo.test": "Otto Outsider",
    "owner@uz.test": "Dilshod Egasi",
}


class Client:
    def __init__(self, base: str):
        self.base, self.s = base.rstrip("/"), requests.Session()

    def call(self, method: str, path: str, **kw) -> requests.Response:
        self.s.get(f"{self.base}/api/auth/csrf/")
        headers = {"X-CSRFToken": self.s.cookies.get("csrftoken", ""), "Referer": self.base + "/"}
        return self.s.request(method, f"{self.base}/api{path}", headers=headers, timeout=120, **kw)

    def login(self, email: str, display_name: str) -> None:
        r = self.call("POST", "/auth/register/", json={"email": email, "password": PASSWORD, "display_name": display_name})
        if r.status_code >= 400:
            r = self.call("POST", "/auth/login/", json={"email": email, "password": PASSWORD})
            r.raise_for_status()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8080")
    ap.add_argument("--limit", type=int, default=0, help="max files per organization (0 = all)")
    args = ap.parse_args()

    clients = {}
    for email, name in USERS.items():
        clients[email] = c = Client(args.base)
        c.login(email, name)
        print(f"user  {email}")

    for org_name, (folder, members) in ORGS.items():
        owner_email = next(e for e, r in members.items() if r == "owner")
        owner = clients[owner_email]
        orgs = {o["name"]: o for o in owner.call("GET", "/orgs/").json()}
        org = orgs.get(org_name) or owner.call("POST", "/orgs/", json={"name": org_name}).json()
        org_id = org["id"]
        print(f"org   {org_name} ({org_id})")
        for email, role in members.items():
            if role == "owner":
                continue
            r = owner.call("POST", f"/orgs/{org_id}/members/", json={"email": email, "role": role})
            print(f"  member {email} as {role}: {r.status_code}")

        existing = {d["original_filename"] for d in owner.call("GET", f"/orgs/{org_id}/documents/?page_size=100").json().get("results", [])}
        files = sorted((CORPUS / folder).glob("*")) if (CORPUS / folder).exists() else []
        for f in files[: args.limit or None]:
            if f.name in existing:
                continue
            for _ in range(5):
                with f.open("rb") as fh:
                    r = owner.call("POST", f"/orgs/{org_id}/documents/", files={"file": (f.name, fh)})
                if r.status_code != 429:
                    break
                time.sleep(int(r.headers.get("Retry-After", 30)))  # upload throttle
            print(f"  upload {f.name} ({f.stat().st_size // 1024} KB): {r.status_code} {'' if r.ok else r.text[:150]}")
            time.sleep(0.2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
