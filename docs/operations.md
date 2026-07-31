# Operations: The Hedron Crawler

Reference for the scheduled crawl workflow — what it does, how to read its
logs, and how to tell a real failure from an upstream hiccup.

## The Workflow

`.github/workflows/run-crawler.yml` defines a single workflow named **Hedron
Crawler**. It runs hourly (`cron: '0 * * * *'`) and can also be triggered by
hand via `workflow_dispatch`. It needs `contents: write` because the last step
pushes the crawl results back to `main`.

Steps, in order:

| Step | What it does |
|------|--------------|
| Checkout code | `actions/checkout@v4` |
| Install uv | `astral-sh/setup-uv@v5`, with caching enabled |
| Set up Python | `uv python install 3.10` |
| Install dependencies | `uv sync` |
| Set git identity | `git config` from the `USER` and `MAIL` secrets |
| Run crawl pipeline | `uv run python crawl.py` |
| Commit and push crawl artifacts | `git add assets/ archetypes/ info.json`, commit, rebase, push |

The commit step is marked `if: always()`, so **a failed crawl still commits and
pushes whatever it managed to collect**. A red X does not mean data was lost.

Pushing to `main` triggers the separate `pages-build-deployment` workflow, which
is why you see two runs per hour in the run list.

### Secrets

| Secret | Used for |
|--------|----------|
| `USER` | git `user.name` on the commit |
| `MAIL` | git `user.email` on the commit |
| `TOKEN` | Authenticating the GitHub API listing in the Pauperwave crawler |

`GITHUB_TOKEN` is also passed to the crawl step as `${{ github.token }}` and
acts as the fallback when `TOKEN` is unset — `src/pipeline.py` reads
`TOKEN` first, then `GITHUB_TOKEN`.

## Reading the Exit Code

`crawl.py` exits non-zero whenever any source failed, *after* writing out
everything the other sources produced:

```python
if failed_sources:
    raise SystemExit(f"\nSource(s) failed: {', '.join(failed_sources)}")
```

This is deliberate. A source going dark would otherwise look identical to a
quiet "no new data" run, so the pipeline surfaces it as a failed run instead.

`src/pipeline.py` catches `requests.exceptions.RequestException` around the MTGO
crawl and appends `"mtgo"` to `failed_sources` rather than raising, so the
Pauperwave import still runs. In other words:

- **Failed run, `Source(s) failed: mtgo`** — MTGO was unreachable. Pauperwave
  data still imported and was pushed. Usually transient.
- **Failed run, some other error** — worth reading the full log.
- **Successful run** — every source responded, whether or not there was new data.

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
www.mtgo.com timed out. (connect timeout=60)`. Wizards' server is intermittently
unreachable from GitHub runners. Nothing to fix; the next hourly run normally
recovers. Only worth investigating if it persists across many consecutive runs.

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
uv run crawl.py
uv run crawl.py --refresh-scryfall   # force re-download of Scryfall oracle data
```

Set `TOKEN` in the environment to authenticate the Pauperwave listing. The
Scryfall bulk download is cached under `.cache/oracle-cards.jsonl.gz`.
