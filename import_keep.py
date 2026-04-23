import hashlib
import time
import uuid
import json
import requests
import shutil
from pathlib import Path
from datetime import datetime, timezone

# ============================================================
# CONFIG — edit these 2 things only
# ============================================================
TAKEOUT_DIR = ""

# Paste the full cookie string from browser headers here
COOKIES_RAW =""
# ============================================================

def make_auth_header():
    ts = str(int(time.time()))
    sapisid = sapisid1 = sapisid3 = ""
    for part in COOKIES_RAW.split(";"):
        p = part.strip()
        if p.startswith("SAPISID="):
            sapisid = p.split("=", 1)[1].strip()
        elif p.startswith("__Secure-1PAPISID="):
            sapisid1 = p.split("=", 1)[1].strip()
        elif p.startswith("__Secure-3PAPISID="):
            sapisid3 = p.split("=", 1)[1].strip()
            
    def h(sid):
        return hashlib.sha1(f"{ts} {sid} https://keep.google.com".encode()).hexdigest()
        
    return f"SAPISIDHASH {ts}_{h(sapisid)} SAPISID1PHASH {ts}_{h(sapisid1)} SAPISID3PHASH {ts}_{h(sapisid3)}"

def make_timestamp():
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

def make_request_header():
    ts = int(time.time() * 1000)
    req_id = f"request.r{uuid.uuid4().hex[:12]}.{ts}"
    session_id = f"s--{ts}--{uuid.uuid4().int % 2000000000}"
    return {
        "requestId": req_id,
        "clientSessionId": session_id,
        "clientPlatform": "ANDROID",
        "clientVersion": {"major": "5", "minor": "22", "build": "0", "revision": "0"},
        "capabilities": [
            {"type": "LB"}, {"type": "TR"}
        ]
    }

# Verify SAPISID found
sapisid_check = ""
for part in COOKIES_RAW.split(";"):
    p = part.strip()
    if p.startswith("SAPISID="):
        sapisid_check = p.split("=", 1)[1].strip()
        break

if not sapisid_check:
    print("ERROR: Could not find SAPISID in cookies.")
    exit()

print(f"SAPISID found: {sapisid_check[:10]}...")

API_KEY = "AIzaSyDE7NHMUZfMoJVu-YNkK-7AXFSuL1Q9gKE"
BASE_URL = "https://notes-pa.clients6.google.com/notes/v1"

HEADERS = {
    "authorization": make_auth_header(),
    "content-type": "application/json",
    "cookie": COOKIES_RAW,
    "x-origin": "https://keep.google.com",
    "origin": "https://notes-pa.clients6.google.com",
    "referer": "https://notes-pa.clients6.google.com",
    "x-requested-with": "XMLHttpRequest",
    "x-goog-authuser": "1",
}

# --- STEP 1: FETCH EXISTING LABELS FROM KEEP (WITH PAGINATION) ---
print("\nFetching labels from Keep account...")
label_name_to_id = {}
target_version = None
page = 1

while True:
    print(f"Fetching page {page} of existing Keep data...")
    HEADERS["authorization"] = make_auth_header()
    
    body = {
        "nodes": [],
        "clientTimestamp": make_timestamp(),
        "requestHeader": make_request_header()
    }
    if target_version:
        body["targetVersion"] = target_version

    res = requests.post(
        f"{BASE_URL}/changes?alt=json&key={API_KEY}",
        json=body,
        headers=HEADERS
    )

    if not res.ok:
        print(f"Could not fetch labels: {res.status_code} — {res.text[:150]}")
        break

    data = res.json()
    
    user_info = data.get("userInfo", {})
    labels_data = user_info.get("labels", [])
    
    for lbl in labels_data:
        name = lbl.get("name", "")
        nid = lbl.get("mainId", "") 
        if name and nid:
            label_name_to_id[name] = nid

    truncated = data.get("truncated", False)
    target_version = data.get("toVersion")

    if not truncated:
        break
        
    page += 1
    time.sleep(0.3)

print(f"\nFound {len(label_name_to_id)} unique labels: {list(label_name_to_id.keys())}")


# --- STEP 2: FIND ALL JSON NOTE FILES & SETUP RESUME FOLDER ---
json_files = [
    f for f in Path(TAKEOUT_DIR).glob("*.json")
    if f.name != "Labels.json"
]

SUCCESS_DIR = Path(TAKEOUT_DIR) / "imported_success"
SUCCESS_DIR.mkdir(exist_ok=True)

print(f"\nFound {len(json_files)} notes left to import.\n")


# --- STEP 3: IMPORT NOTES ---
imported = 0
skipped = 0
failed = 0

for filepath in json_files:
    with open(filepath, "r", encoding="utf-8") as f:
        note = json.load(f)

    # Skip trashed notes
    if note.get("isTrashed", False):
        print(f"  SKIP (trashed): {filepath.name}")
        skipped += 1
        # Move trashed files so they don't clog up future runs
        filepath.rename(SUCCESS_DIR / filepath.name)
        continue

    title = note.get("title", "").strip()
    content = ""

    # Safely convert checklists to standard text
    if "listContent" in note:
        lines = []
        for item in note["listContent"]:
            checkbox = "[x]" if item.get("isChecked") else "[ ]"
            text_val = item.get("text", "")
            lines.append(f"{checkbox} {text_val}")
        content = "\n".join(lines)
    else:
        content = note.get("textContent", "").strip()

    if not title and not content:
        print(f"  SKIP (empty): {filepath.name}")
        skipped += 1
        # Move empty files so they don't clog up future runs
        filepath.rename(SUCCESS_DIR / filepath.name)
        continue

    # --------------------------------------------------------
    # THE ULTIMATE BRUTE-FORCE HACK
    # Since the API drops body text, we shove everything into the title.
    # --------------------------------------------------------
    if content:
        if not title:
            title = content
        else:
            # Both exist. Merge them with a double newline!
            title = f"{title}\n\n{content}"
            
        # Clear the content since it is now safely stored inside the title
        content = ""

    # Map label names from Takeout JSON to the correct Keep IDs
    label_names = [lbl["name"] for lbl in note.get("labels", [])]
    label_ids = [{"labelId": label_name_to_id[l]} for l in label_names if l in label_name_to_id]
    
    missing = [l for l in label_names if l not in label_name_to_id]
    if missing:
        print(f"  WARNING: Labels not found in new Keep account: {missing}")

    # Build note payload
    note_id = str(uuid.uuid4()).replace("-", "")[:20]
    note_payload = {
        "id": note_id,
        "type": "NOTE", 
        "title": title,
        "text": content, # This will now be empty, avoiding the API bug entirely
        "labelIds": label_ids,
        "timestamps": {
            "created": make_timestamp(),
            "updated": make_timestamp(),
        }
    }

    HEADERS["authorization"] = make_auth_header()
    res = requests.post(
        f"{BASE_URL}/changes?alt=json&key={API_KEY}",
        json={
            "nodes": [note_payload],
            "clientTimestamp": make_timestamp(),
            "requestHeader": make_request_header()
        },
        headers=HEADERS
    )

    if res.ok:
        # Keep console output clean
        display_title = title.split('\n')[0][:40] + "..." if len(title) > 40 else title.replace('\n', ' ')
        print(f"  OK: '{display_title}' | Labels Attached: {label_names or 'none'}")
        imported += 1
        
        # RESUME MAGIC: Move the successfully imported file to the success folder
        filepath.rename(SUCCESS_DIR / filepath.name)
        
    else:
        print(f"  FAIL ({res.status_code}): '{title[:40]}' — {res.text[:150]}")
        failed += 1

    time.sleep(1)

# --- SUMMARY ---
print(f"\n{'='*40}")
print(f"Done!")
print(f"  Imported : {imported}")
print(f"  Skipped  : {skipped}")
print(f"  Failed   : {failed}")
print(f"{'='*40}")
