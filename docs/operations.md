# Operations: The Hedron Crawler

Reference for the scheduled crawl workflow — what it does, how to read its
logs, and how to tell a real failure from an upstream hiccup.

## The Workflow

`.github/workflows/run-crawler.yml` defines a single workflow named **Hedron
Crawler**. It is scheduled four times an hour (`cron: '7,22,37,52 * * * *'`,
offset from `:00` because GitHub delays jobs that pile up on the hour) and
can also be triggered by hand via `workflow_dispatch`. GitHub may still skip
or delay scheduled runs on public repositories; the extra ticks are there so
a missed slot does not mean a missed afternoon. It also runs on every push
to `main`, to redeploy the site with the new code.

The crawler writes nothing to git. Tournament data lives in the
[`vedalken/merchantscroll`](https://huggingface.co/datasets/vedalken/merchantscroll)
Hugging Face dataset (`src/hub.py`, card in `docs/huggingface-dataset.md`);
player, deck and metagame profiles are rebuilt from it on each deploy, and the
site is published as a Pages artifact.

Steps, in order:

| Step | What it does |
|------|--------------|
| Checkout code | `actions/checkout@v4` |
| Install uv | `astral-sh/setup-uv@v5`, with caching enabled |
| Set up Python | `uv python install 3.10` |
| Install dependencies | `uv sync` |
| Run crawl pipeline | `uv run python crawl.py` (`--build-only` on pushes): pull the dataset, crawl, rebuild, push changed files back to the dataset |
| Stage site / Upload site | copy the checkout minus dotfiles into `_site`, upload it as the Pages artifact |
| Deploy (second job) | `actions/deploy-pages` |

Scheduled runs deploy only when the crawl changed the dataset; pushes and
manual runs always deploy. `crawl.py` sets the `deploy` output after the data
is pushed, so **a crawl that fails afterwards still ships what it collected**,
while a failed dataset pull deploys nothing. MTGO timeouts are retried, logged,
and left green so a busier schedule does not flood Action failure emails.
Unexpected errors still fail the job.

If a deploy fails after the dataset was updated, the next scheduled run sees
no change and will not redeploy: trigger the workflow by hand.

### Secrets

| Secret | Used for |
|--------|----------|
| `HF_TOKEN` | Write access to the Hugging Face dataset |
| `TOKEN` | Authenticating the GitHub API listing in the Pauperwave crawler |

`GITHUB_TOKEN` is also passed to the crawl step as `${{ github.token }}` and
acts as the fallback when `TOKEN` is unset — `src/pipeline.py` reads
`TOKEN` first, then `GITHUB_TOKEN`.

## Reading the Exit Code

`crawl.py` still prints `Source(s) failed: …` after writing whatever the other
sources produced. It only exits non-zero for unexpected sources. An MTGO timeout
after retries is logged and the job stays green, because that is the usual
GitHub-runner hiccup and a red X was inbox spam.

`src/pipeline.py` catches `requests.exceptions.RequestException` around the MTGO
crawl and appends `"mtgo"` to `failed_sources` rather than raising, so the
Pauperwave import still runs. The listing fetch retries timeouts and empty stub
pages a few times before giving up. In other words:

- **Green run, `Source(s) failed: mtgo`** — MTGO was unreachable after retries.
  Pauperwave data still imported and was pushed. Investigate only if this
  message repeats across many consecutive hours.
- **Failed run** — unexpected error or a non-MTGO source failed. Read the log.
- **Successful run with no source warning** — every source responded, whether
  or not there was new data.

## Inspecting Runs

Requires the [GitHub CLI](https://cli.github.com/) authenticated with the `repo`
and `workflow` scopes:

```bash
gh auth status                      # verify login and scopes
gh run list --limit 20              # recent runs, newest first
gh run view <run-id> --log-failed   # only the step that failed
gh run view <run-id> --log          # the whole log
gh run watch <run-id>               # follow a run in progress
gh workflow run "Hedron Crawler"    # trigger a run by hand
```

To narrow the list to the crawler and skip the Pages deploys:

```bash
gh run list --workflow run-crawler.yml --limit 20
gh run list --workflow run-crawler.yml --status failure
```

Runs are also browsable at
[github.com/chumpblocckami/merchantscroll/actions](https://github.com/chumpblocckami/merchantscroll/actions).

### If `gh` is installed as a snap

The snap build is strictly confined and cannot execute host binaries such as
`/usr/bin/ssh-keygen`, so `gh auth login` fails with `fork/exec ... permission
denied` if you pick the SSH protocol and ask it to generate a key. Choose HTTPS
instead:

```bash
gh auth login -h github.com -p https -w
```

Do not prefix this with `sudo`. Confinement applies to root as well, and the
credentials would land in root's snap home rather than
`~/snap/gh/current/.config/gh/hosts.yml`.

## Known Failure Modes

**MTGO connection timeout.** `MTGO source unavailable: ... Connection to
www.mtgo.com timed out. (connect timeout=60)`. The listing request is retried
a few times; if it still fails, the run stays green and logs
`Source(s) failed: mtgo`. Wizards' server is intermittently unreachable from
GitHub runners. Only worth investigating if that warning persists across many
consecutive hours.

**`GitHub rejected the token (401); retrying the listing without
authentication.`** The `TOKEN` secret is expired, revoked, or missing the
required scope. `src/pauperwave_crawler.py` falls back to an anonymous listing,
so the import keeps working — but anonymous GitHub API access is limited to 60
requests/hour shared across the runner's IP, versus 5000/hour authenticated.
This message does **not** fail the run, so it can go unnoticed for a long time.
Fix by regenerating the secret. To check whether it is happening:

```bash
gh run view <run-id> --log | grep "rejected the token"
```

**Node 20 deprecation warnings.** `actions/checkout@v4` and
`astral-sh/setup-uv@v5` target Node 20, which GitHub has deprecated and now
force-runs on Node 24. Harmless today; clears by bumping to `checkout@v5` and
`setup-uv@v6`.

## Running the Pipeline Locally

```bash
uv run python -m src.hub pull       # only download the dataset into assets/pauper
uv run crawl.py                     # pull, crawl, rebuild
uv run crawl.py --build-only        # pull and rebuild the derived files
uv run crawl.py --refresh-scryfall  # force re-download of Scryfall oracle data
```

`crawl.py` pushes changed files to the dataset only when `HF_TOKEN` is set;
without it, local crawls stay local. Set `TOKEN` in the environment to
authenticate the Pauperwave listing. The
Scryfall bulk download is cached under `.cache/oracle-cards.jsonl.gz`.
