# Investigator Agent Design — Level 1

**Status:** Narration-only slice implemented and wired into the CLI
(`--narrative-output`). OpenAI backend adapter still deferred.

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
- No OpenAI credentials are wired in this slice. The backend is a swappable
  callable; a real OpenAI-backed implementation is a thin adapter added later
  behind the same interface.

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

## CLI wiring

`recovery_witness.cli` accepts an optional `--narrative-output PATH`. When
given, `cli.main()`:

1. publishes the sealed case file and oracle exactly as before (unchanged
   two-file collision-safe publication);
2. only then calls `narrate(sealed_case_file, null_narrator)`;
3. writes the result atomically with the same `write_case_file` helper used
   for the case file.

`validate_artifact_paths` additionally rejects a `narrative_output` that
collides with the case or oracle path. A narration failure happens strictly
after the case and oracle are durably published, so it can never roll back
or discard already-sealed work (honest degradation: an optional artifact
failing must not destroy the core result).

Covered by `tests/test_narrator.py::CliNarrativeTests`.

## Open items

- Real OpenAI-backed `Narrator` adapter (needs key management and network
  policy, out of scope here). It plugs into the same `Narrator` callable used
  by `cli.py` — no boundary change expected.
- Whether the narrative artifact gets its own hash for tamper-evidence
  (likely yes, but it must never feed back into `sha256` of the case file —
  that would re-introduce the model into the decision path).
