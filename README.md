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

The current research basis is available in
[`docs/investigacion-inicial.md`](docs/investigacion-inicial.md). It is a
working research document, not a specification or a report of completed
experiments.

## Why this problem matters

Imagine a simulated ECU receiving a configuration update. An unexpected reboot
occurs in the middle of the operation.

When the system starts again, it finds a record saying that the operation began.
That record does not prove that the operation finished, that persisted data is
intact, or that it is safe to continue. Recovery of the process is not the same
as recovery of the device state.

Recovery Witness is intended to make that distinction explicit and testable.

This is not intended to be another OTA update installer. Existing update and
rollback systems address important parts of reliable deployment. Recovery
Witness focuses on the complementary question: after an interrupted operation,
what state can be reconstructed, and what evidence is strong enough to support
or withhold a conclusion?

## Research direction

The investigation is expected to explore:

- persistent transition records with verifiable integrity;
- controlled fault injection at different points in an operation;
- state reconstruction after restart;
- independent observations from a simulated device, rather than relying only
  on the operation's own journal;
- reproducible experiments that can distinguish competing explanations;
- temporal evidence from QNX 8.0, including `tracelogger` and `TraceEvent()`
  where available;
- explicit abstention when the evidence is insufficient.

The final state model, criteria, and decision levels are deliberately not
specified yet. They should be derived from experiments rather than chosen only
because they make a demo convenient.

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

## QNX and the evidence model

QNX is part of the research question, not just a deployment label. A QNX-based
prototype could provide application evidence alongside kernel and runtime trace
evidence. The two sources may be correlated, but they should not be treated as
the same observation automatically.

This matters because a filesystem can be internally consistent while the
higher-level ECU transaction is not. A persisted payload, a journal entry, and
a successful reboot may all be real observations without proving that the
intended state transition completed.

## Exploratory architecture

```text
                    QNX 8.0 environment
  simulated ECU + fault injection + application and kernel traces
                              |
                              v
                  Evidence and experiment layer
              reconstruction, invariants, controlled tests
                         /                    \
                        /                      \
                       v                        v
             LLM investigator             Experimental ML
          hypotheses and test choice     temporal patterns and anomalies
```

The OpenAI Responses API is one candidate integration point for structured tool
use and investigator outputs. The exact interface is still open. The important
boundary is that the agent can request observations and experiments through
controlled tools, but cannot write configuration to an ECU.

## ML as an open research question

ML is an experimental research line, not yet a promised classifier or safety
decision-maker. The question is whether learned methods can reveal temporal or
state-transition patterns that a reasonable set of explicit invariants does not
cover, especially when the failure mechanism differs from the examples already
studied.

Possible directions include anomaly detection and transition-pattern discovery,
but no dataset, model family, feature representation, or training regime is
chosen yet. Those choices belong after the evidence model and first fault
campaign have been investigated.

The evaluation must be able to show that ML adds no value. A deterministic rule,
a statistical baseline, or an explicit abstention may be the correct result. Any
claim of discovering a new failure mode would require a separate evaluation
scenario and a reproducible experiment; recognizing a memorized demonstration
case would not count.

External automotive and time-series datasets may be useful as methodological
references or transfer tests, but they are not being selected here as training
data. The recovery-specific evidence should come from controlled experiments
whose failure mechanism and ground truth are known independently of the model.

## Working evidence vocabulary

The investigation currently separates four kinds of statements:

| Category | Meaning |
| --- | --- |
| Observation | Evidence obtained from the simulator, trace, journal, or controlled experiment |
| Hypothesis | A possible explanation proposed by the investigator |
| Test | A reproducible action intended to distinguish hypotheses |
| Conclusion | A bounded statement supported by the collected evidence |

Keeping these categories separate is central to the project. A model-generated
hypothesis is not an observation, and a successful restart is not by itself a
conclusion about the recovered device state.

## Scope decisions

- Go is not a project requirement at this stage.
- The prototype targets a simulated ECU before any claim about real hardware.
- The LLM may investigate and request observations through controlled tools, but
  it may not write ECU configuration.
- ML remains exploratory; its data, model, and evaluation design are still open.
- No production-safety or real-device guarantee is claimed by this provisional
  repository.

## Repository contents

```text
ECU/
├── LICENSE       # MIT license
├── README.md     # provisional project statement
├── docs/         # research material and future technical design documents
├── skills/       # machine-learning research skills
└── .venv/        # local development environment, ignored by Git
```

Implementation, experiments, tests, and technical design documents will be
added after the investigation establishes the state model and evidence criteria.
