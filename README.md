# Daily Athletics Brief — automated

Pulls the feeds every morning, sorts them into **National, Youth & Grassroots,
Para, International, Events to keep an eye on**, publishes a page and emails it
to you. Free to run: GitHub Actions is the scheduler, GitHub Pages is the site.

## Fastest setup — one command

Install the [GitHub CLI](https://cli.github.com), then from this folder:

```bash
gh auth login          # sign in as yourself, once
bash bootstrap.sh
```

It creates the repo, asks for your email settings, stores them as encrypted
secrets, switches on the website, and triggers the first run. Your app password
is typed by you and goes straight to GitHub — it is never written to disk or
committed.

## Manual setup, if you'd rather

**1.** Put these files in a new GitHub repo. Public = free Pages hosting.

**2.** Settings → Secrets and variables → Actions, add:

| Secret | What goes in it |
|---|---|
| `SMTP_HOST` | e.g. `smtp.gmail.com` |
| `SMTP_PORT` | `465` for SSL, `587` for TLS |
| `SMTP_USER` | your email address |
| `SMTP_PASS` | an **app password**, not your account password |
| `MAIL_FROM` | the sending address |
| `MAIL_TO` | where the brief lands |

Gmail needs 2-factor authentication on first, then generate an app password
under Google Account → Security. Outlook and Fastmail work the same way.

**3.** Settings → Pages → deploy from branch → `main` → `/docs`.

**4.** Actions tab → Run workflow → check the email arrives.

## The schedule

`.github/workflows/daily-brief.yml`, the line `cron: "30 5 * * *"`. That's 06:30
BST and 05:30 GMT, since cron runs on UTC — adjust in October if the arrival
time matters. GitHub's scheduler can fire a few minutes late; it is not a
guarantee of the exact minute.

## Checking your feeds

```bash
pip install feedparser pyyaml
python daily_brief.py --check      # tests every source, sends nothing
python daily_brief.py --no-email   # builds the page only
```

I could not test the feed URLs when I wrote them — my sandbox has no network —
so run `--check` first and fix anything marked DEAD in `feeds.yml`. Dead feeds
are skipped at runtime and named at the foot of the brief rather than breaking
the run.

## Tuning it

- **Section order** — the order of the blocks under `sections:` in `feeds.yml`
  is the order they appear in the brief. Move them and the output moves.
- **Routing** — `routing:` catches para and youth stories arriving through
  general feeds, so a T38 result carried by a national outlet still files under
  Para rather than National. Add terms as you spot misfiles.
- **Watchlist** — names there get pulled to the top of their section and marked
  in amber.
- **Events** — section five reads the `events:` list and drops anything in the
  past automatically. Top it up every few weeks.
- **`WINDOW_HOURS`** in `daily_brief.py` — 26, so consecutive runs overlap
  slightly and nothing falls through the gap.

## What this does and does not do

It gathers and sorts. It does not judge, verify or write. Headlines arrive as
published, unchecked. **Every mark still needs confirming against World
Athletics or the meet's own results before it goes on air.**

For the judgement layer — what leads, what the storyline is, which stat to have
ready — paste the morning's page into a chat and run the standing brief prompt
against it. The machine sweeps; the analysis stays a conversation.
