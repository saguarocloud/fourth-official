# Contributing

## Workflow

1. Branch from `main`. One pull request per logical slice of work; keep it reviewable.
2. Work test-first: write a failing test, make it pass with the simplest code, then refactor.
3. Run `make check` (lint, format, types, tests with coverage, infrastructure policy tests).
4. Open a pull request using the template. `main` is protected: changes land only by squash merge
   after the `ci-ok` check passes.

## Review gates

Every pull request gets two reviews before merge, and every finding is fixed (or deferred with a
tracked item in `docs/PLAN.md`):

- **Code review:** correctness, readability, function and file size, error handling, immutability,
  test coverage of new behaviour.
- **Security review:** secrets and credentials, input validation at boundaries, authentication and
  authorization, injection (SQL, prompt, command), dependency vulnerabilities, least-privilege
  Azure roles, data exposure in logs and outputs.

## Standards

- Python: ruff, mypy `--strict`, pytest (warnings are errors), coverage of at least 80%.
- TypeScript: strict mode, ESLint with zero warnings, Prettier, Vitest, coverage of at least 80%.
- Infrastructure: Bicep lint with zero warnings; policy tests in `infra/tests` guard cost and
  security rules (scale to zero, no admin credentials, least-privilege roles).
- Commits: one-line conventional commit subjects (`feat:`, `fix:`, `chore:` …).
- Data: everything is synthetic. Never use real league, club, player or broadcaster names, logos
  or match data.
