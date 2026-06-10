# GitHub Upload Checklist

## Before uploading

- [ ] Rename the repository folder if needed.
- [ ] Decide whether to keep the MIT License or replace it with another license.
- [ ] Add the accepted paper citation once the official metadata is available.
- [ ] Do not upload private or restricted raw datasets unless the dataset license allows redistribution.
- [ ] Do not upload the manuscript PDF unless you are sure it can be publicly shared.

## Local test

```bash
pip install -r requirements.txt
pytest -q
python scripts/run_demo.py --algorithm linear --orders 500 --vehicles 50
python scripts/compare_algorithms.py
```

## Recommended first commit

```bash
git init
git add .
git commit -m "Initial M3PR ride-sharing reproduction scaffold"
git branch -M main
git remote add origin https://github.com/<your-name>/<repo-name>.git
git push -u origin main
```

## Recommended repository description

```text
Reproduction scaffold for an efficient price-aware route-planning framework for large-scale ride-sharing.
```

## Suggested topics

```text
ride-sharing, route-planning, order-insertion, dynamic-programming, vehicle-pruning, transportation, m3pr
```
