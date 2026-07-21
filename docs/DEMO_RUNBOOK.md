# Claros hero demo runbook

Use the synthetic `demo/hero_worksheet.pdf`. This is the supported demo scope,
not a claim of arbitrary-PDF understanding.

```powershell
python scripts/verify_demo.py
$env:CLAROS_DEMO_MODE='true'
python scripts/run_demo.py
```

Open `http://127.0.0.1:8000/app`, upload the hero worksheet, select subpart
`a`, type a natural answer, review the exact candidate text, and explicitly
confirm it. The validated line receives the write; select the drawing task to
show automatic side-panel routing. Export only after the answer is written.

The demo mode is a hash-bound deterministic replay and is visibly documented
as such. With funded API access, unset `CLAROS_DEMO_MODE` and use the normal
live compiler path. Typed interaction is the guaranteed path; microphone or
provider failure does not bypass confirmation or writing authorization.
