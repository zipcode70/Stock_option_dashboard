# Setting Up the Options Indicators Dashboard on GitHub (manual, one-time)

This mirrors the exact same setup pattern you already used for your two GEX
dashboards, so if you've done that before this will feel familiar. Once set
up, you can trigger a fresh run for any ticker from your phone or any
computer — no Python installation needed on your end, GitHub does the work.

You'll need: a GitHub account (free tier is fine).

---

## Step 1 — Download the project files

You should have a folder/zip called `options_indicators_dashboard` containing:

```
options_indicators_dashboard/
├── .github/workflows/on-demand-indicators.yml
├── scripts/compute_indicators.py
├── site/ (index.html, styles.css, app.js, data/)
├── requirements.txt
├── README.md
├── HANDOVER.md
├── DECISION_GUIDE.md
└── GITHUB_SETUP.md   (this file)
```

If you received this as a `.zip`, extract it on your computer first — you
need the actual folder, not the zip, for Step 3.

**Important:** the `.github` folder starts with a dot, which some file
browsers hide by default. Make sure "show hidden files" is on (or trust that
it's there — it is) so you don't accidentally leave it out when uploading.

---

## Step 2 — Create a new GitHub repository

1. Go to [github.com/new](https://github.com/new).
2. Pick a repository name, e.g. `options-indicators-dashboard`.
3. Set visibility to **Public** (GitHub Pages' free tier requires a public
   repo, unless you have GitHub Pro/Team/Enterprise).
4. Do **not** check "Add a README file" — you're uploading your own.
5. Click **Create repository**.

---

## Step 3 — Upload the project files

1. On your new (empty) repo's page, click **uploading an existing file**
   (the link in the "Quick setup" box), or use **Add file → Upload files**.
2. Drag the *entire contents* of the `options_indicators_dashboard` folder
   into the upload box — either drag the whole folder in (most browsers
   preserve the folder structure this way) or drag each top-level item
   (`.github`, `scripts`, `site`, `requirements.txt`, `README.md`,
   `HANDOVER.md`, `DECISION_GUIDE.md`) in together. The key thing is that
   `.github/workflows/on-demand-indicators.yml` ends up at exactly that path
   in the repo — GitHub only recognizes workflow files in that exact folder.
3. Scroll down and click **Commit changes**.
4. After it uploads, click into the `.github/workflows/` folder in the repo
   to confirm `on-demand-indicators.yml` actually made it in — this is the
   single most common thing to get missed.

---

## Step 4 — Give Actions permission to commit data back to the repo

The workflow needs to write the ticker's data file back into the repo after
computing it.

1. Go to **Settings** (top nav of the repo) → **Actions** → **General** (left
   sidebar).
2. Scroll to **Workflow permissions**.
3. Select **Read and write permissions**.
4. Click **Save**.

---

## Step 5 — Turn on GitHub Pages

1. Still in **Settings**, go to **Pages** (left sidebar).
2. Under **Build and deployment → Source**, select **GitHub Actions**
   (not "Deploy from a branch").
3. Nothing else to configure here — the workflow itself handles publishing.

---

## Step 6 — Run it once to confirm everything works

1. Go to the **Actions** tab (top nav).
2. If prompted "Workflows aren't being run on this forked repository" or
   similar, click **I understand my workflows, go ahead and enable them**.
3. Click **On-Demand Options Indicators** in the left sidebar.
4. Click the **Run workflow** dropdown button (top right of the list).
5. Type a ticker into the box (e.g. `AAPL`).
6. Click the green **Run workflow** button.
7. Wait about a minute. Refresh the Actions tab — you should see the run
   go from a yellow dot (in progress) to a green check (success).
8. If it fails (red X), click into the run to read the error log — see
   Troubleshooting below.

---

## Step 7 — Find your live dashboard link

1. Go to **Settings → Pages**. Once the first successful deploy finishes,
   you'll see **"Your site is live at https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/"**
   at the top of that page.
2. Bookmark that link — it's permanent and always shows whichever ticker you
   last ran.

---

## Using it going forward

Every time you want to check a different ticker:

1. Actions tab → **On-Demand Options Indicators** → **Run workflow** → type
   the ticker → **Run workflow**.
2. Wait ~1 minute, then refresh your GitHub Pages link (or use the
   dashboard's own ticker box + Load button if that ticker's data file
   already exists from a previous run).

There's no schedule and nothing runs automatically — exactly like your GEX
dashboards, this only updates when you trigger it.

---

## Troubleshooting

- **Red X on the run, log mentions "Permission denied" or "403" on the push
  step**: You skipped Step 4. Go set Workflow permissions to "Read and write"
  and re-run.
- **Red X, log mentions the ticker has no options or "no price history"**:
  The ticker either doesn't exist, isn't optionable, or `yfinance` had a
  transient hiccup — double-check the spelling and try again. `yfinance` is
  an unofficial data source and occasionally has brief outages.
- **Pages says "There isn't a GitHub Pages site here"**: The first workflow
  run hasn't completed successfully yet, or Step 5 (Source = GitHub Actions)
  wasn't set. Confirm Step 5, then re-run the workflow.
- **Workflow doesn't show up under the Actions tab at all**: The
  `.github/workflows/on-demand-indicators.yml` file didn't upload to the
  right path (Step 3). Check the file exists at exactly that path in the
  repo's file browser.
- **You want to remove the sample data files that came with the project**
  (AAPL/TSLA/SPY from testing): harmless to leave them, or delete
  `site/data/*.json` before your first real run if you'd rather start clean
  — the workflow will just add whichever tickers you actually run.
