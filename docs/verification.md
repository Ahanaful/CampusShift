# Phase 1 verification

Verified locally on Windows with Python 3.12 and a portable Node.js 22.22.0 runtime:

- Frontend dependency installation completed and generated `frontend/package-lock.json`; npm reported zero vulnerabilities.
- `npm run build` passed with Vite 7.3.7.
- Backend import printed `CampusShift API`.
- `python -m unittest discover -s tests -v` passed all four API/CORS tests.
- A live Vite server returned HTTP 200 for the page and transformed React module.
- A request to `http://127.0.0.1:5173/api/health` passed through Vite to a live Uvicorn backend and returned the exact expected health object.
- `git diff --check` passed (Git emitted only an LF-to-CRLF informational warning).

The verification servers were stopped afterward. No cloud resources were accessed or deployed, and nothing was committed or pushed.

## Environment limitations

Node/npm were absent from PATH, so verification used a portable Node runtime in ignored `.local/`. Regular development requires installing Node or adding a local runtime to PATH. The Windows sandbox blocked Python package setup and esbuild child processes; those steps succeeded with tool execution outside the sandbox.

No browser preview tool was available. Visual rendering, responsive layouts in a browser, and clicking the offline/retry status flow were not verified. Follow the root README's manual connection checks to verify those states.
