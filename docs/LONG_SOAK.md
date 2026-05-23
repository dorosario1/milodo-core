# MILODO Long Soak

Run a 24h soak:

```powershell
py -3 scripts/run_long_soak.py --interval 300 --cycles 288
```

PowerShell wrapper:

```powershell
.\scripts\run_long_soak.ps1 -Interval 300 -Cycles 288
```

Resume after interruption:

```powershell
py -3 scripts/run_long_soak.py --interval 300 --cycles 288 --resume
```

Outputs:

- `reports/soak/latest_state.json`
- `reports/soak/long_term_report.json`
- `reports/soak/soak_report_*.json`
- `reports/soak/snapshots/`

Stop with `Ctrl+C`. The runner writes an interrupted report and a snapshot.

