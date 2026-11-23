# Investigator Agent Design — Level 1

**Status:** Narration-only slice implemented and wired into the CLI
(`--narrative-output`, `--narrator-backend {null,openai}`). The OpenAI
adapter was live-verified in a development session on 2026-11-22 against the
real API: the call succeeded and the sealed case file (`payload` and
`sha256`) was byte-identical before and after narration. That live check was
a manual smoke test, not a committed automated test — committed coverage for
the OpenAI adapter (`tests/test_narrator_openai.py`,
`tests/test_narrator.py::CliNarrativeTests`) is mock-only and makes no real
network call, so CI stays offline and deterministic.

## What already exists

`recovery_witness.investigator.investigate()` is a deterministic, rule-based
investigator. Given mechanic text and public bench observations, it:

- validates the public-evidence boundary (rejects hidden oracle keys, mixed
  execution identities, broken event chains);
- runs `experiment.assess()`, a closed-form hypothesis-elimination over the
  three fixed host fixture signatures (H1 power drop, H2 transport loss, H3
  incomplete recovery);
- returns a `case-file.v1` payload with `hypotheses`, `bench_assessment`,
  `next_observation`, and a hardcoded `decision = "ABSTAIN"`.

`harness.build_case_file()` then wraps that payload in a canonical envelope
and seals it with SHA-256 (`sealed-case-file.v1`). This already matches the
architecture this project requires: the decision path is deterministic,
float-free, and sealed before anything else can touch it.

## What is still missing

The README names an "OpenAI-backed investigator" as part of the intended
architecture: something that organizes mechanic evidence, proposes rival
mechanisms in prose, and explains why a given experiment was requested. None
of that exists yet — `investigate()` only returns structured data, no
narrative.

## Non-goals for this slice

- The LLM does not choose, rank, or filter hypotheses. The fixture catalogue
  is closed (3 signatures); `experiment.assess()` remains the only place that
  decides `matched_hypothesis` / `candidate_prefixes`.
- The LLM does not change `decision` or `decision_scope`. Both stay
  hardcoded to `ABSTAIN` and the vehicle-evidence disclaimer.
- The LLM never receives bench internals beyond what the sealed payload
  already exposes (no oracle fields were ever in that payload — enforced at
  `investigate()` and again at `build_case_file()`).
- The OpenAI adapter (`recovery_witness.narrator_openai`) is a thin stdlib
  (`urllib`) client behind the same `Narrator` callable interface; it does
  not add a package dependency or a new manifest file.

## Boundary

```
investigate() ──▶ payload (case-file.v1)
                      │
                      ▼
build_case_file() ──▶ sealed-case-file.v1   (sha256 computed HERE)
                      │
        ┌─────────────┴──────────────┐
        │   read-only summary          │
        ▼                              │
narrator.render_prompt()                │
        │                              │
        ▼                              │
Narrator(prompt) ──▶ prose             │
        │                              │
        ▼                              │
narrator.narrate() ──▶ case-narrative.v1  (stored BESIDE the case file,
                                            never merged into the sealed
                                            payload or envelope)
```

The seal is computed strictly before any narrator call. Swapping the narrator
backend (a template-only `null_narrator` for tests, an Ollama adapter, a
hosted API adapter later) must change only the prose in `case-narrative.v1`.
The sealed `payload` and its `sha256` are identical regardless of which
backend ran — this is enforced by
`tests/test_narrator.py::test_narration_never_changes_the_seal`, which runs
two different backends over the same sealed case file and asserts the case
file side is byte-identical.

## Module: `recovery_witness.narrator`

- `build_narration_summary(case_file)` — reads a `sealed-case-file.v1`
  envelope only; raises if the schema tag is missing or if a hidden oracle
  key is present (defense in depth; this should already be unreachable given
  the upstream boundary, but the narrator must not assume it).
- `render_prompt(summary)` — builds a prompt that lists the case id,
  mechanic observations, hypotheses, the matched hypothesis or remaining
  candidates, the next requested observation, and the fixed decision/scope,
  with an explicit instruction that these figures are fixed and must not be
  altered, contradicted, or extended with a vehicle diagnosis.
- `Narrator` — a `Callable[[str], str]` protocol. `null_narrator` is the
  default, deterministic, offline implementation used in tests and until a
  real backend is wired.
- `narrate(case_file, narrator=null_narrator)` — returns a
  `case-narrative.v1` dict: `{"schema_version", "case_id", "text",
  "backend"}`. This is the artifact stored alongside the sealed case file,
  never inside it.

## Module: `recovery_witness.narrator_openai`

`make_openai_narrator(*, model=DEFAULT_MODEL, api_key_env=DEFAULT_API_KEY_ENV,
timeout=20.0)` returns a `Narrator` callable backed by the OpenAI chat
completions API over stdlib `urllib`:

- the API key is read from `os.environ[api_key_env]` **inside the call**,
  never captured as an attribute of the returned callable, so it cannot be
  logged or serialized by printing the narrator itself;
- every raised error message is built from a short, pre-checked detail
  string (status code, network error reason, "malformed response") — never
  from the request/response body or headers, so the key cannot leak through
  an exception;
- `tests/test_narrator_openai.py` mocks `urllib.request.urlopen` and asserts
  a canary key value appears in the `Authorization` header and nowhere else
  (not the URL, not the body, not any raised exception message).

## CLI wiring

`recovery_witness.cli` accepts an optional `--narrative-output PATH` plus
`--narrator-backend {null,openai}` (default `null`), `--narrator-model`, and
`--narrator-api-key-env`. When `--narrative-output` is given, `cli.main()`:

1. publishes the sealed case file and oracle exactly as before (unchanged
   two-file collision-safe publication);
2. only then calls `narrate(sealed_case_file, narrator)`, where `narrator` is
   `null_narrator` or `make_openai_narrator(...)` depending on
   `--narrator-backend`;
3. writes the result atomically with the same `write_case_file` helper used
   for the case file.

`validate_artifact_paths` additionally rejects a `narrative_output` that
collides with the case or oracle path. A narration failure happens strictly
after the case and oracle are durably published, so it can never roll back
or discard already-sealed work (honest degradation: an optional artifact
failing must not destroy the core result).

Covered by `tests/test_narrator.py::CliNarrativeTests` (both backends, mocked).

## Open items

- Whether the narrative artifact gets its own hash for tamper-evidence
  (likely yes, but it must never feed back into `sha256` of the case file —
  that would re-introduce the model into the decision path).
- Whether the OpenAI adapter needs retry/backoff for transient errors; none
  is implemented now (a failed call simply raises).
