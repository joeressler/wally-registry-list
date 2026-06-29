# Wally Registry List

A simple desktop app to browse all packages in the [Wally](https://wally.run/) registry of Roblox Luau packages. Data is loaded from the official [wally-index](https://github.com/UpliftGames/wally-index) GitHub repository — no Wally API calls.

## Features

- Searchable, sortable list of all Wally packages
- Full metadata and descriptions from the index
- Open package pages on wally.run
- Copy `scope/name@version` dependency specs for `wally.toml`

## Requirements

- Python 3.11+

## Install

```bash
pip install -r requirements.txt
pip install -e .
```

## Run

```bash
python -m wally_registry_list
```

Or after install:

```bash
wally-registry-list
```

## Data source

On first launch (and when the cache is older than 24 hours), the app downloads a single zip archive from GitHub:

`https://github.com/UpliftGames/wally-index/archive/refs/heads/main.zip`

Package metadata is parsed from NDJSON files at `{scope}/{name}` inside that index.

## Cache location

- Index extract: `%LOCALAPPDATA%/WallyRegistryList/index/`
- SQLite database: `%LOCALAPPDATA%/WallyRegistryList/cache.db`

## Optional: GitHub token

Set `GITHUB_TOKEN` to raise GitHub API rate limits for the archive download.

## Links

- [Wally](https://wally.run/)
- [wally-index](https://github.com/UpliftGames/wally-index)
