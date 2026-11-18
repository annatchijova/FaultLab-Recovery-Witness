# Preliminary Development Levels

**Status:** Proposed and exploratory

This document records a preliminary construction sequence for ECU Recovery
Witness. It is a planning document, not an implementation specification. The
levels may change after the first experiments, the host environment is verified,
and the evidence contract is tested.

## Destination

Recovery Witness is intended to become an autonomous investigation system for
interrupted ECU configuration or firmware operations.

The objective is not merely to verify whether an ECU restarted in a plausible
state. The objective is to investigate recovery defects by:

1. collecting and reconstructing evidence;
2. proposing competing explanations;
3. designing experiments that can distinguish or refute those explanations;
4. executing those experiments through controlled tools; and
5. preserving a reproducible forensic case file.

The investigator must preserve the distinction between an observation, a model
hypothesis, an experiment, and a conclusion. A successful reboot is not proof of
a successful state transition, and a persuasive explanation is not evidence.

## Construction sequence

The proposed order follows construction dependencies and experimental decisions,
not increasing feature sophistication.

| Level | Preliminary product | Acceptance question |
| --- | --- | --- |
| 1. End-to-end Investigator | Host simulator, harness, real agent, witness, oracle, evidence bundle, replay, and report/PDF artifact | Can the agent investigate an injected failure, run a discriminating experiment, and produce a verifiable case file without ML? |
| 2. ML Experiment | The same investigator with an optional ML signal | Does ML add useful evidence beyond explicit rules and simpler baselines, or should it be discarded? |
| 3. QNX Investigator | The investigated runtime and native components operating on QNX 8.0, initially targeting QEMU if feasible | Do traces, persistence, fault injection, and reconstruction preserve their meaning on QNX? |
| 4. Adversarial Investigator | Harder cases with contradictory evidence, missing logs, ambiguous confirmation, and rival causes | Does the investigator remain evidence-bound when several explanations fit the visible record? |
| 5. Autonomous Discovery | Autonomous exploration of mechanisms not present in development examples | Can the system find and reproduce a previously withheld defect under blind evaluation with an independent oracle? |

Level 1 and Level 2 are functional development milestones. They are not, by
themselves, a valid final QNX demonstration. Level 3 establishes the execution
evidence needed for that claim. Levels 4 and 5 increase investigative
difficulty after the basic system and platform boundary have been exercised.

## Proposed system boundary

```text
Python agent and proposed Python frontend
  hypotheses, experiment planning, interpretation, case-file presentation
                              |
                    controlled investigation API
                              |
C++17 portable core and adapters
  harness, witness, reconstruction, invariants, oracle, evidence packaging
                              |
        host runtime first, QNX 8.0 runtime later
                              |
             simulated ECU and fault injection
```

### Proposed language allocation

- **C++17:** portable witness and harness core, state reconstruction, invariant
  evaluation, oracle interfaces, event handling, and platform adapters.
- **Python:** investigation agent, OpenAI API integration, experiment planning,
  report orchestration, and the provisional frontend.
- **QNX 8.0:** execution environment for the native components at Level 3.

This is a proposed allocation, not a claim that the toolchain or API boundary
has already been validated. The C++17 core is intended to reduce the semantic
gap between the host prototype and the QNX target. QNX compiler, library,
filesystem, tracing, and IPC compatibility must be checked before this becomes
an accepted implementation decision.

The agent and frontend do not need to move into QNX merely because the witness
does. Keeping investigation orchestration on the host is the current hypothesis;
the target environment should execute the system under investigation and the
native components that require QNX behavior.

## Level 1 — End-to-end Investigator

### Intended product

Level 1 should be a complete investigation loop on the host, not a simulator
that will later receive an agent as a separate project.

An investigation should be able to:

1. prepare a known initial state;
2. execute a configuration operation;
3. inject an interruption without exposing its hidden cause to the agent;
4. collect the evidence visible through the witness interface;
5. reconstruct candidate post-restart states;
6. evaluate explicit invariants and oracle conditions;
7. let the agent formulate rival hypotheses;
8. let the agent request a permitted discriminating experiment;
9. execute that experiment through the harness; and
10. preserve the complete case file for replay and human inspection.

The first level must demonstrate the separation:

```text
experimental truth  !=  evidence visible to the investigator
```

If the agent receives the injected failure label or the simulator's hidden
ground truth directly, the investigation is not meaningful. The harness may
retain hidden truth for oracle evaluation, but that information must remain
outside the investigator's observation channel.

### Actors

| Actor | Responsibility | Authority boundary |
| --- | --- | --- |
| Investigator agent | Form hypotheses, state falsifiable predictions, select permitted tests, revise hypotheses | Cannot write ECU configuration or alter evidence |
| Frontend | Start an investigation, display progress, inspect the case file, request replay/export | Presentation and user control only |
| Harness | Prepare scenarios, inject faults, execute tests, expose controlled observations | May operate the simulated ECU under the experiment contract |
| Witness | Collect evidence, reconstruct state, evaluate invariants, and package artifacts | Does not infer hidden facts from missing evidence |
| Oracle | Evaluate the known experimental outcome for development and acceptance checks | Hidden from the investigator; never replaced by the LLM |
| Case-file writer | Store evidence, hypotheses, tests, results, limits, hashes, and report artifacts | Cannot rewrite original evidence silently |

### Level 1 inputs

- a scenario definition and initial ECU state;
- an operation to execute;
- an allowed fault-injection boundary;
- an observation policy defining what the investigator may request;
- invariant and oracle definitions;
- an experiment budget and safety boundary.

The exact schema is open. The design must ensure that hidden injection labels and
oracle truth are not accidentally included in the agent's context.

### Level 1 outputs

The minimum output is a structured, replayable case file containing:

- investigation and operation identities;
- original observations and their provenance;
- event ordering and clock-domain information;
- hypotheses and their falsifiable predictions before each test;
- requested experiments and actual parameters;
- experiment results and oracle comparisons;
- invariant evaluations;
- hypotheses supported, refuted, or left unresolved;
- explicit limits and abstentions;
- hashes for the relevant artifacts; and
- a human-readable report, with PDF as a candidate export format.

The PDF is a presentation of the case file. It is not the source of truth and
must not be the only artifact retained.

### Level 1 acceptance

Level 1 is complete only when one end-to-end scenario can be replayed from its
recorded inputs and produces a case file whose evidence, hypothesis history,
experiment history, oracle result, and report can be inspected independently.

The first demonstration may use a small number of interruption scenarios. It
must show that the agent can choose an experiment for a reason that is visible
in its prediction, not merely produce a plausible narrative after the result.

## Common evidence contract

The evidence contract is a prerequisite for every level. It should be designed
before Level 1 implementation so that moving from host to QNX does not silently
change the meaning of an event.

Each event should preserve, at minimum:

- execution identity;
- operation identity;
- event identity and sequence position;
- source and observation type;
- clock domain and timestamp semantics;
- causal or correlation references, where known;
- reference to the original evidence artifact;
- schema and contract version; and
- integrity metadata.

Injection labels and oracle truth belong in a separate evaluation channel. They
may be joined for acceptance checks, but they must not be part of the evidence
available to the investigator during an experiment.

The contract should also define what absence means. A missing log is not
automatically proof that an event did not occur, and an inferred event must not
be serialized as if it had been observed directly.

## Level 2 — ML Experiment

Level 2 reuses the Level 1 investigation circuit. It does not create a second
decision path and it does not make ML a prerequisite for the rest of the system.

The experiment asks whether an optional learned signal contributes information
that explicit invariants, deterministic rules, and simpler reference methods do
not provide. The result may be that ML is retained, remains experimental, or is
discarded.

The design must prevent the ML signal from silently becoming the verdict. It may
provide a bounded observation for the investigator and the evidence layer, but
the case file must identify its provenance, scope, and uncertainty. The data
source, model family, feature representation, training procedure, and thresholds
remain open until Level 1 produces suitable evidence.

Acceptance requires a comparison that can fail, including separation by run and
failure mechanism rather than random windows from the same execution. The exact
evaluation protocol is a future decision, not fixed by this document.

## Level 3 — QNX Investigator

Level 3 moves the investigated runtime and required native components to QNX
8.0, initially with QEMU as a possible execution target. The agent and frontend
may remain on the host.

QNX should contribute evidence rather than merely serve as a label. The research
target includes runtime timing, persistence behavior, IPC, user trace events,
kernel traces, and the effects of interruption on reconstruction. The host and
QNX implementations must preserve the common event contract and document any
semantic difference.

An early environment check is part of the plan. It should verify the toolchain,
available QNX APIs, tracing path, persistence behavior, IPC requirements, and
QEMU feasibility before substantial Level 1 or Level 2 assumptions become
expensive. This check is risk reduction, not an attempt to build Level 3 early.

Level 3 acceptance requires evidence that the same investigation meaning is
preserved on QNX. A successful compilation or boot alone is not sufficient.

## Level 4 — Adversarial Investigator

Level 4 increases the difficulty of the investigation rather than simply adding
components. Scenarios should include combinations such as:

- several rival causes compatible with the initial evidence;
- incomplete or reordered logs;
- ambiguous confirmations;
- valid persisted data with insufficient transition evidence;
- delayed or misleading observations; and
- experiments that are safe but uninformative.

Acceptance focuses on evidence discipline: the investigator must state what it
knows, what it hypothesizes, what test it chose and why, and when it cannot
distinguish the remaining explanations. It must not manufacture certainty to
complete the report.

## Level 5 — Autonomous Discovery

Level 5 evaluates discovery under a blind or sealed evaluation design. The
candidate failure mechanism, scenario details, or relevant combination should
not be present in development examples or the investigator's direct context.

The success condition is not that the agent announces a bug. It must produce a
reproducible experiment, preserve the evidence chain, and provide an independent
oracle or checker that confirms the defect. Controls and negative cases are
required to distinguish discovery from a false positive or a replay of a known
pattern.

## Demonstration options

The final demonstration format is intentionally open. Candidate formats include:

1. **Contradictory recovery:** a journal says a write finished while independent
   state evidence leaves completion unresolved.
2. **Hypothesis discrimination:** two explanations fit the initial evidence and
   the agent selects the smallest experiment that separates them.
3. **Three interruption points:** the same operation is interrupted before
   confirmation, after persistence but before confirmation, and after matching
   final evidence.
4. **ML decision point:** the optional signal is compared with explicit rules and
   the project visibly keeps or rejects it based on evidence.
5. **Discovery replay:** a hidden failure is found, then reproduced from the
   preserved case file with an independent checker.

The choice should be made after Level 1 produces a real case file and after the
QNX feasibility check narrows what can be demonstrated honestly.

## Open decisions

The following items remain deliberately unresolved:

- the exact Level 1 scenario and interruption mechanism;
- the common event and case-file schema;
- the first host simulator boundary;
- the C++17/QNX toolchain and adapter constraints;
- the Python agent and frontend interface;
- whether PDF export is generated in the first complete loop;
- the ML task, data, model, and evaluation design;
- the final QNX target configuration; and
- the demonstration format.

These are research decisions, not missing implementation details to be guessed
away. Each should be revisited when the preceding evidence exists.
