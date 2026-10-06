# Operations: The Hedron Crawler

Reference for the scheduled crawl workflow — what it does, how to read its
logs, and how to tell a real failure from an upstream hiccup.

## The Workflow

`.github/workflows/run-crawler.yml` defines a single workflow named **Hedron
Crawler**. It is scheduled four times an hour (`cron: '7,22,37,52 * * * *'`,
offset from `:00` because GitHub delays jobs that pile up on the hour) and
can also be triggered by hand via `workflow_dispatch`. GitHub may still skip
or delay scheduled runs on public repositories; the extra ticks are there so
a missed slot does not mean a missed afternoon. It needs `contents: write`
because the last step pushes the crawl results back to `main`.

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

Pushing to `main` triggers the separate `pages-build-deployment` workflow.
A crawl that finds nothing does not commit, so Pages only runs when data
actually changed. MTGO timeouts are retried, logged, and left green so a
busier schedule does not flood Action failure emails. Unexpected errors
still fail the job.

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

**A crawl commit touching hundreds of profile files.** Derived artifacts —
`assets/pauper/index.json`, `pools.json`, the per-player and per-archetype
profiles, and `meta/timeline.json` — are deterministic: rebuilding them from
unchanged raw data must produce byte-identical files. If a commit rewrites
hundreds of profiles while adding one tournament, something has started leaking
iteration order into output. The usual causes are reading `Path.glob` without
sorting it (directory order differs between machines) and sorting by a key that
is not a total order, such as `date` alone when a whole league week shares one.
`TestDerivedArtifactDeterminism` in `tests/test_unit.py` guards this by
rebuilding under a reversed file order and comparing the results.

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
