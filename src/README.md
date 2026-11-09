# Legacy entry points retired

Version 2 consolidates the former numbered scripts into the tested
`rbi_intelligence` package. This prevents independent scripts from silently
using different event windows or stale output files.

Run the whole analysis from the repository root:

```bash
python -m rbi_intelligence run
```

The previous implementation and results remain available in Git history at
commit `9fcf90ab42d4ed91f5e136d0e2a055c98a68043f`. They must not be mixed with
the regenerated version 2 outputs.
