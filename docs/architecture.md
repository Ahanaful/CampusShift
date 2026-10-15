# Phase 1 architecture

The React application requests `GET /api/health`. In development Vite forwards `/api` to FastAPI at `http://127.0.0.1:8000`. An optional `VITE_API_BASE_URL` supports independently hosted frontends. FastAPI allows the configured local browser origins through CORS.

The status component checks on mount and on manual retry, validates the response, times out after six seconds, and cancels pending requests when unmounted. There is no persistence, authentication, scheduling, or AWS integration.

Future scheduling logic belongs in `scheduler/`, separate from API routes. Infrastructure belongs in `infrastructure/` so sandbox resources can eventually be recreated. Deployment will require a permitted HTTP entry point and existing sandbox roles; API Gateway, Cognito, and creating IAM roles must not be assumed.
