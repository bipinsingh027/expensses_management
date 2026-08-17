# Site Expense Manager — Local Edition

A single-user, fully offline expense manager for site/construction expenses.
Runs on your own Windows laptop. Uses **SQLite** for the database and stores
uploaded bank statements, receipts and screenshots on your local disk.

- No cloud database.
- No login required (single user).
- No internet connection required after install.
- One-click Start / Stop from the desktop.

---

## 1. First-time installation on Windows

You only need to do this once.

### 1.1 Install the prerequisites

1. **Python 3.11 or newer** — <https://www.python.org/downloads/windows/>
   - During install, tick **"Add Python to PATH"**.
2. **Node.js 18 LTS** — <https://nodejs.org/en/download>

Restart your PC once so the PATH updates apply.

### 1.2 Get the source code

You have three easy options — pick whichever suits you:

**Option A — Download ZIP from Emergent (simplest)**
1. In the Emergent workspace, open the top menu → **Download code** (or *Export project*).
2. Save the ZIP to your laptop and unzip it into a permanent folder such as
   `C:\SiteExpenseManager`.

**Option B — Push to GitHub, then clone on the laptop**
1. In the Emergent workspace, use **Push to GitHub** to create the repo.
2. On your laptop, install Git for Windows (<https://git-scm.com/download/win>).
3. In `C:\` right-click → *Git Bash here* → run
   `git clone https://github.com/<you>/<repo>.git SiteExpenseManager`.

**Option C — Copy the folder manually**
Copy the entire project folder (with `backend`, `frontend`, `windows`,
`README.md` inside) from wherever you have it to your laptop.

The folder should look like this:
```
SiteExpenseManager\
    backend\
    frontend\
    windows\
        Install.bat
        Start Site Expense Manager.bat
        Stop Site Expense Manager.bat
    README.md
```

### 1.3 Run the installer

Open the `windows` folder and **double-click `Install.bat`**.

It will:
- Create a Python virtual environment inside `backend\.venv`
- Install the Python packages the backend needs
- Install the frontend packages and build the frontend for offline use
- Place **Site Expense Manager** and **Stop Site Expense Manager** shortcuts on
  your Desktop

Grab a coffee — the first run downloads a few hundred MB and can take
5–10 minutes. When it finishes you will see `Install complete`.

---

## 2. Starting the application

**Double-click `Start Site Expense Manager.bat`.**

- A black console window opens (leave it open — it *is* the app).
- Your browser opens automatically at **<http://localhost:5555>**.
- If the browser does not open, open it yourself and go to that address.

The app is ready when the Dashboard shows numbers.

---

## 3. Stopping the application

You have two easy options:

- Close the black console window that says *"Site Expense Manager"*, **or**
- Double-click `Stop Site Expense Manager.bat`.

All your data remains safely stored on disk — nothing is lost.

The Stop script also drops an `AutoBackup_<date>.zip` into your data folder's
`reports\` subfolder every time you stop the app, so a recent copy is always
sitting next to your database.

---

## 4. Where your data lives

Everything is kept in **one folder** so it is easy to back up or move:

```
C:\Users\<you>\Documents\SiteExpenseManager\
    site_expense_manager.sqlite3     ← the database (all transactions, sites, rules, etc.)
    statements\                       ← original CSV / XLSX / PDF bank statements
    documents\                        ← receipt screenshots attached to transactions
    reports\                          ← generated Excel / PDF exports and backup ZIPs
```

You can copy this folder anywhere as a manual backup at any time.

If you would like the data folder to be somewhere else, edit
`windows\Start Site Expense Manager.bat` and change the
`SEM_DATA_DIR=` line.

---

## 5. Backup and restore

### Backup
1. Open the app → **Backup & restore** in the left menu.
2. Click **Download backup ZIP**.
3. Save the ZIP to OneDrive, an external drive, or wherever you keep backups.

The ZIP contains the SQLite database plus **all** uploaded statements and
receipt files.

### Restore
1. Open the app → **Backup & restore**.
2. Under **Restore from backup**, choose your previously saved backup ZIP.
3. Click **Restore now**.

The current database and uploaded files are replaced with the ones from the
ZIP. (You will be asked to confirm before it happens.)

---

## 6. Updating the application

When a new version of the source code is available:

1. Stop the app.
2. Replace the `backend` and `frontend` folders with the new versions.
   **Do not touch `Documents\SiteExpenseManager` — that folder is your data.**
3. Double-click `Install.bat` again to update the packages and rebuild the
   frontend.
4. Start the app as usual.

Tip: take a backup ZIP before an update, just in case.

---

## 7. Frequently asked questions

**Does it need the internet?**
No. After install everything runs on your laptop. The app happily works with
Wi-Fi turned off.

**Do I need to keep the app running all day?**
No. Start it when you need it, stop it when you are done. Your data stays on
disk between sessions.

**Can two people use the same install?**
No — this build is designed for a single user on a single laptop. If two
people need to see the same data, share the backup ZIP or install on a
shared machine.

**Can I change the port?**
Yes. Edit `Start Site Expense Manager.bat` and change `SEM_PORT=5555` to any
free port. The Stop script uses the same value.

**Where is the database file exactly?**
`%USERPROFILE%\Documents\SiteExpenseManager\site_expense_manager.sqlite3`.
It is a normal SQLite file — you can open it with DB Browser for SQLite if
you ever want to look inside.

---

## 8. Troubleshooting

| Symptom | Try this |
|---|---|
| `Python was not found` when running `Install.bat` | Install Python and tick *Add Python to PATH*, then reboot. |
| Browser shows *This site can't be reached* | Wait a few extra seconds after Start — the first launch can take up to 15s. |
| Port 5555 already in use | Change `SEM_PORT` in the Start and Stop scripts to e.g. `5678`. |
| App looks empty after start | You may have deleted sample data. Upload a statement or add a site/account to begin. |
| Something feels broken | Take a backup ZIP first, then re-run `Install.bat`. |

Enjoy!
