# online-mahalla auto-filler

Selenium (Microsoft Edge) automation for the [online-mahalla.uz](https://www.online-mahalla.uz)
workspace. The project fills household records and populates the
"Хонадон аъзолари" tab with up to 30 entries whose relationship is "Бошқа".

Two independent runners share one persistent browser profile, so manual login is
required only once.

Developer: terv1q (Emir-Veliyev Rustem Aliyevich)

## Runners

| Runner | Input table | Result |
|---|---|---|
| `python -m src.household_filler` | `data/input/household_entries.xlsx` | Creates a household from a cadaster number: cadaster lookup, PINFL and birth date, dictionaries, phone number, "Ижтимоий-иқтисодий ҳолат" checkboxes, "Сақлаш" |
| `python -m src.family_filler` | `data/input/family_members.xlsx` | Adds entries to the "Хонадон аъзолари" tab of each household: document data from the table, ЖШШИР lookup, "Маълумоти" set to "Маълумоти йўқ", generated mobile number |

Both runners keep their progress. A restart skips completed households and never
reuses a row that has already been entered.

## Project layout

```
online-mahalla-auto-filler/
├── src/
│   ├── core/                       shared infrastructure
│   │   ├── browser.py              Selenium automation
│   │   ├── js.py                   JavaScript helpers
│   │   ├── logs.py                 logging configuration
│   │   ├── pacing.py               adaptive pacing
│   │   ├── paths.py                path constants
│   │   ├── profile.py              session profile
│   │   ├── selectors.py            DOM selectors
│   │   ├── settings.py             global settings
│   │   ├── state.py                state management
│   │   ├── timing.py               timing constants
│   │   └── utils.py                utility functions
│   ├── household_filler/           runner 1, household records
│   │   ├── automation.py           main automation logic
│   │   ├── cli.py                  command-line interface
│   │   ├── config.py               configuration
│   │   └── model.py                Excel I/O and data models
│   └── family_filler/              runner 2, family members ("Бошқа")
│       ├── automation.py           main automation logic
│       ├── cli.py                  command-line interface
│       ├── config.py               configuration
│       ├── js.py                   family-specific JavaScript
│       ├── members.py              members state management
│       ├── model.py                Excel I/O and data models
│       └── api.py                  core API re-exports
├── tools/                          DOM diagnostics, development only
│   ├── diag_member_modal.py
│   ├── diag_member_options.py
│   ├── diag_member_add.py
│   └── diag_search_network.py
├── data/
│   ├── input/                      input Excel tables
│   └── streets/streets_source.txt  street list saved from the site page
├── var/                            runtime output
│   ├── state/                      progress, registries, ignore lists
│   ├── reports/                    Excel reports
│   ├── logs/                       run logs and action traces
│   └── screenshots/                screenshots taken on errors
├── browsers/edge_profile_v3/       persistent Edge profile, not tracked by git
├── docs/                           architecture notes and legacy scripts
├── requirements.txt
└── LICENSE
```

`var/` and `browsers/` are created on the first run. All paths are resolved
relative to the project root, so a runner can be started from any directory.

## Requirements

* Python 3.10 or newer
* Microsoft Edge

Selenium Manager resolves the matching driver automatically.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

On the first run the browser opens the login page. Sign in manually (ERI or
OneID). The session is stored in `browsers/edge_profile_v3`; later runs reuse it.

```bash
python -m src.household_filler
python -m src.family_filler
```

Common options. Run `--help` for the full list.

| Option | Meaning |
|---|---|
| `--limit N` | Process at most N households per run |
| `--start-row N` | First row of the sheet to read |
| `--cadaster CODE` | Process households whose cadaster contains this substring |
| `--street-id ID` | Process a single street by its `street_id` |
| `--resume` | Continue from the saved progress file |
| `--retry-ignored` | Household runner only, also retry records on the ignore list |
| `--no-trace-js` | Do not log every JavaScript call to the action log |
| `--debug-select` | Print the HTML of list elements that could not be selected |

## How it works

1. The district street list comes from the `tables/survey_homes` page and from
   `data/streets/streets_source.txt`. Streets with `street_id=0` and unnamed
   streets are skipped.
2. Each street is opened and the household links (`/forms/survey_homes/{id}`)
   are read.
3. Completed households are skipped without opening a form. Their state is kept
   in `var/state/`.
4. Streets and forms are opened in reusable tabs; unused tabs are closed.
5. Every step is written to `var/logs/*_actions.log` with timings: method entry
   and exit, algorithm stage, JavaScript result.
6. Site responses are read from the page itself. BootstrapVue toasts
   ("Хабар", "Диққат", "Хатолик") are classified by type, and API HTTP errors are
   captured separately.
7. Errors do not stop a run:
   * "Хатолик" or `Request failed with status code 400`: the row is marked as
     used and is not retried, and the dialog is closed before the next row;
   * "So'rovlar ko'payib ketdi. N soniya kuting": the runner pauses for N
     seconds, keeps the row in the queue and retries it;
   * browser window closed: the browser restarts, the household is reopened and
     the counter is re-read;
   * a series of failures: the form is reloaded so the next row starts from a
     clean state.
8. Request timeouts adapt to the site. A slower response raises them, a fast
   response lowers them immediately.

## Output

* `var/reports/household_report.xlsx`, `var/reports/family_report.xlsx`:
  per-run report sheets, successful records, errors, skipped rows
* `var/state/*.json`: progress, used table rows, street state
* `var/state/*.txt`: cadaster registries and ignore lists
* `var/logs/*.log`: run log and JavaScript action trace
* `var/screenshots/`: screenshots taken on errors

## Diagnostics

Scripts in `tools/` open a specific form and dump its DOM: dialog fields,
dictionary options, search requests. Use them when the site markup changes.

```bash
python tools/diag_member_modal.py
python tools/diag_member_options.py
```

## Architecture

See `docs/ARCHITECTURE.md` for the data flow, the DOM contracts used by the
selectors, the failure classification table and the known technical debt.

## Limitations

* Both runners contain their own copy of the browser layer. See the technical
  debt section in `docs/ARCHITECTURE.md`.
* The site is built on Vue 2, BootstrapVue and Select2. Native `<select>`
  options carry empty labels, so values are resolved through the rendered
  Select2 markup.
* Logging is verbose by default. Watch the size of `var/logs/*_actions.log`
  during long runs, or pass `--no-trace-js`.
* Input tables and the browser profile are excluded from version control. They
  must be supplied locally.

## License

Released under the MIT License. See `LICENSE`.

Copyright (c) 2026 Emir-Veliyev Rustem Aliyevich (terv1q)
