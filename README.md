# KeepImport
A python script to import notes from one keep account to another

# Google Keep Takeout Importer

A robust Python script to import notes from a Google Keep Takeout export (`.json` files) into a new Google Keep account. 

Because Google Keep lacks an official public API for importing notes, this script interacts with Keep's undocumented internal API. It handles the specific quirks of the Keep backend, including rate limits, session expiration, and formatting bugs, to ensure your data transfers safely.

## ✨ Features
* **Preserves Body Text:** Spoofs the Android client header to prevent Google's web-client API from silently dropping standard text bodies.
* **Smart Fallbacks:** If a note lacks a title but has body text, the script automatically promotes the text to the title (or merges them) to prevent the server from generating a blank note.
* **Checklist Conversion:** Automatically and safely converts Keep checklists (which use complex internal node structures) into readable, text-based lists (e.g., `[x] Done`, `[ ] To Do`).
* **Resume-Friendly:** Successfully imported notes are physically moved to an `imported_success` folder. If your cookies expire or you hit a rate limit, simply run the script again and it will pick up exactly where it left off!
* **Label Mapping:** Automatically fetches your existing labels from the new Keep account and attaches them to your imported notes.

---

## 🛠 Prerequisites

1. **Python 3.x** installed on your machine.
2. The `requests` library. Install it via terminal/command prompt:
   ```bash
   pip install requests
   ```
3. A **Google Takeout** export of your old Google Keep account. Extract the `.zip` file so you have a folder full of `.json` note files.

---

## 🚀 Step-by-Step Setup

### Step 1: Configure the Script
Open the Python script (`import_keep.py`) in a text editor. At the very top, you will see a configuration section. You only need to edit two variables:

1. Set `TAKEOUT_DIR` to the exact path of your extracted Google Keep Takeout folder (the folder containing all the `.json` files).
2. Set `COOKIES_RAW` to your active Google Keep session cookie (see Step 2 below).

### Step 2: Get Your Keep Authentication Cookie
To allow the script to write to your *new* Google Keep account, you need to provide your active browser cookie. 

1. Open Google Chrome (or Edge/Firefox) and log into your **new** Google Keep account.
2. Press `F12` (or `Cmd + Option + I` on Mac) to open the **Developer Tools**.
3. Go to the **Network** tab.
4. Refresh the page (`F5` or `Cmd + R`).
5. In the Network tab, click on any request named `changes` or `notes` in the list.
6. Scroll down to the **Request Headers** section.
7. Find the row labeled `cookie:`. Right-click the massive string of text next to it and copy it entirely (it usually starts with `__Secure-` or `SAPISID=`).
8. Paste this entire string into the `COOKIES_RAW` variable in the Python script.

### Step 3: Run the Importer
Open your terminal or command prompt, navigate to the folder containing the script, and run it:

```bash
python3 import_keep.py
```

---

## ⚠️ Troubleshooting & FAQ

* **401 UNAUTHENTICATED Error:** Your cookie has either expired or was copied incorrectly. Grab a fresh cookie from your browser and try again.
* **429 RATE LIMIT EXCEEDED Error:** You imported notes too fast. Stop the script and wait **30 to 45 minutes**. The script includes a built-in `time.sleep(2.5)` to prevent this, do not lower this number for large batches!
* **Script crashed halfway through:** No problem! Successfully imported notes are moved to `imported_success`. Update your cookie and run the script again; it will automatically process only the remaining files.

---
