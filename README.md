# ECU Recovery Witness

**A recovery auditor for interrupted electronic-control-unit operations.**

ECU Recovery Witness investigates what can be demonstrated about an ECU's state
after a configuration operation is interrupted by a reboot, lost communication,
or power failure.

The central question is not whether the process started again. It is whether the
post-recovery state is coherent and whether the available evidence is sufficient
to continue safely.

> An interrupted operation is not successful merely because the process ran
> again after a restart.

## Project status

This repository is in the investigation and architecture phase. The definitive
state model, evidence criteria, verdict levels, and implementation boundaries
have not been fixed yet. The goal of this README is to capture the working
problem statement and the hypotheses that will guide that investigation.

## Why this problem matters

Imagine a simulated ECU receiving a configuration update. An unexpected reboot
occurs in the middle of the operation.

When the system starts again, it finds a record saying that the operation began.
That record does not prove that the operation finished, that persisted data is
intact, or that it is safe to continue. Recovery of the process is not the same
as recovery of the device state.

Recovery Witness is intended to make that distinction explicit and testable.

## What the project is intended to investigate

The prototype is expected to explore:

- persistent transition records with verifiable integrity;
- controlled fault injection at different points in an operation;
- state reconstruction after restart;
- reproducible observations and explicit abstention when the evidence is
  insufficient;
- temporal measurements on QNX 8.0, including evidence from `tracelogger` and
  `TraceEvent()` where available;
- a simulated device that provides observations independent of the operation's
  own journal.

The final criteria are deliberately not specified yet. They should be derived
from experiments rather than chosen only because they make the demo convenient.

## Demonstration hypothesis

Run the same configuration operation three times and interrupt it at different
points:

1. the operation never reaches confirmation;
2. data persists, but confirmation is missing;
3. the final device state and the independent evidence agree.

The system should distinguish these situations without inventing missing facts
and without treating a successful restart as proof of a successful recovery.

This experiment is a target for the prototype, not a claim that the repository
already implements it.

## An AI investigator, not an ECU writer

The project is being reframed around an active investigation agent. The LLM is
intended to formulate competing hypotheses about an interrupted recovery, select
the next useful observation, and request controlled experiments against the
simulated ECU.

For example, given an incomplete temporal sequence, a journal entry claiming
that a write finished, and a persisted state that differs from the expected
configuration, the investigator might consider:

- a partial write;
- a premature confirmation;
- an out-of-order persisted record;
- incomplete recovery; or
- data corruption.

These are hypotheses, not observations. The agent must seek discriminating
evidence and preserve the difference between what the model proposes and what
the experiment verifies.

The LLM will not write configuration data to a real ECU. Its authority is limited
to investigation planning and evidence analysis through controlled interfaces.
Any future operational decision must be grounded in an explicit, auditable
evidence policy rather than in the model's narrative confidence.

## Planned architecture

```text
QNX 8.0 simulated ECU
  operations, restarts, persisted state, and temporal traces
                    |
                    v
Evidence and experimentation layer
  reproducible observations, invariants, and fault injection
                    |
          +---------+---------+
          |                   |
          v                   v
OpenAI Responses API     Experimental ML
hypotheses, tool use,    anomaly and temporal-pattern
test selection, analysis discovery
```

The OpenAI Responses API is a candidate integration point for structured tool
use and investigator outputs. QNX tracing is a candidate source of temporal
evidence beyond simulator-generated logs.

## ML research direction

ML is an experimental research line, not yet a promised classifier or safety
decision-maker. Two initial directions are under consideration:

### Anomaly detection

Train or fit a model on normal executions and evaluate whether it identifies
temporal sequences that become anomalous after injected interruptions.

### Transition-pattern discovery

Study whether a model can identify combinations of states and events associated
with inconsistent recovery, including cases that do not match the known failure
examples.

Any claim that ML discovered a new failure mode will require a separate
evaluation set, adversarial cases, and a reproducible experiment. Memorizing the
three demonstration scenarios will not count as discovery.

## Design boundary under investigation

The project will distinguish at least these categories during research:

| Category | Meaning in the investigation |
| --- | --- |
| Observation | Evidence obtained from the simulator, trace, journal, or controlled experiment |
| Hypothesis | A possible explanation proposed by the investigator |
| Test | A reproducible action intended to distinguish hypotheses |
| Conclusion | A bounded statement supported by the collected evidence |

The names and final decision levels are intentionally left open until the
evidence model and experiments have been studied.

## Scope decisions

- Go is not a project requirement at this stage.
- The prototype targets a simulated ECU before any claim about real hardware.
- The LLM may investigate and request observations through controlled tools, but
  it may not write ECU configuration.
- ML is exploratory and must earn any discovery claim through held-out,
  reproducible evaluation.
- No production-safety or real-device guarantee is claimed by this provisional
  repository.

## Repository contents

```text
ECU/
├── LICENSE       # MIT license
├── README.md     # provisional project statement
├── skills/       # engineering and research skills used during development
└── .venv/        # local development environment, ignored by Git
```

Implementation, experiments, tests, and technical design documents will be
added after the investigation establishes the state model and evidence criteria.
