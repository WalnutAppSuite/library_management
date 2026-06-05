# Capture tooling (docs media)

Generates the screenshots (`docs/assets/*.png`) and feature GIFs
(`docs/assets/recordings/*.gif`) by driving the real Frappe desk UI with Playwright against
seeded demo data. Maintainers only — not shipped with the app.

## Prerequisites

- A running site reachable at `http://localhost:8000` (`bench use <site> && bench start`).
- Node 18+.
- Demo data + a capture login user seeded by `scripts/seed_demo.py` (see below).

## One-time setup

```bash
cd docs/_capture
npm install
npx playwright install chromium
# On a minimal Linux box without the browser's system libs and no sudo, fetch them locally:
#   mkdir -p syslibs && cd syslibs
#   apt-get download libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
#     libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
#     libpango-1.0-0 libcairo2 libasound2t64 libatspi2.0-0t64 libxshmfence1
#   for d in *.deb; do dpkg -x "$d" root; done
#   export LD_LIBRARY_PATH="$PWD/root/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH"
```

## Seed demo data

```bash
bench --site <site> console < scripts/seed_demo.py
```

Creates a clean demo student (`DEMO001`), 5 demo books, issue/return/reissue history, and a
capture login user (`library-demo@example.com`). No real student PII is used.

## Run

```bash
node capture.js          # screenshots -> docs/assets, videos -> ./_videos
node ../_capture/convert # (or the inline ffmpeg loop) -> docs/assets/recordings/*.gif
```

`node_modules/`, `syslibs/`, `_videos/`, and `*.deb` are git-ignored — only the scripts are
committed.
