# Preliminary Development Levels

**Status:** Proposed and exploratory

This document describes a preliminary construction sequence for Recovery Witness
as an automotive electronic-fault investigation laboratory. It is not an
implementation specification. The levels may change after the first host
experiments, the QNX environment is checked, and the evidence contract is tested.

## Destination

Recovery Witness is intended to connect observations from a mechanic and a real
vehicle with controlled experiments on a QNX-based virtual-ECU bench.

The laboratory does not inspect the real vehicle's hidden state. It explores
possible mechanisms and produces conditional predictions that can help the
agent request better observations. The mechanic remains responsible for
choosing and safely performing measurements on the vehicle.

The investigator should be able to:

1. organize real-vehicle observations;
2. formulate competing mechanisms that are compatible with those observations;
3. predict what each mechanism would produce in the laboratory;
4. choose experiments that can distinguish the mechanisms;
5. preserve the difference between simulated evidence and vehicle evidence; and
6. produce a reproducible diagnostic plan and forensic case file.

## Construction sequence

The order follows construction dependencies and experimental risk, not a ladder
of increasingly impressive features.

| Level | Preliminary product | Acceptance question |
| --- | --- | --- |
| 1. End-to-end laboratory | Mechanic-facing case input, AI investigator, host harness, witness, human review, evidence bundle, replay, and report/PDF candidate | Can the agent investigate a case, compare rival mechanisms in the bench, and produce a bounded diagnostic plan without pretending the simulation proves the vehicle fault? |
| 2. Early ML experiment | The same investigator with an optional ML signal | Does ML add useful evidence beyond explicit rules and simpler baselines, or should it be rejected? |
| 3. QNX bench | Native experimental components and runtime instrumentation on QNX 8.0, initially targeting QEMU if feasible | Do persistence, IPC, interruptions, and traces preserve the meaning of the host experiment? |
| 4. Contrastive investigation | Comparison of real observations with predictions from multiple mechanisms and requests for discriminating measurements | Does the agent choose useful next observations while preserving uncertainty? |
| 5. Autonomous discovery | Autonomous exploration of the bench for previously withheld defects | Can the system find and reproduce a bench defect under blind evaluation with an independent oracle? |

Level 1 and Level 2 are development products. They do not constitute a final
QNX demonstration. Level 3 establishes the QNX execution evidence. Levels 4 and
5 increase the difficulty of the investigation after the basic laboratory and
platform boundary have been exercised.

## Proposed system boundary

```text
Mechanic and real vehicle
  symptoms, DTCs, reports, freeze frames, measurements, history
                              |
                              v
Python investigator and proposed Python frontend
  evidence organization, hypotheses, predictions, test requests, reports
                              |
                    controlled experiment API
                              |
C++17 portable bench and adapters
  virtual ECUs, fault injector, witness, reconstruction, oracle, evidence
                              |
             host runtime first, QNX 8.0 later
```

### Proposed language allocation

- **C++17:** portable native bench, virtual ECU components, fault injection,
  witness logic, reconstruction, invariants, oracle interfaces, and platform
  adapters.
- **Python:** investigator agent, OpenAI API integration, experiment planning,
  case-file orchestration, and provisional frontend.
- **QNX 8.0:** target runtime for native bench components at Level 3.

This is a proposed allocation, not a validated toolchain decision. QNX compiler,
library, filesystem, tracing, IPC, and QEMU compatibility must be checked before
the boundary is treated as stable.

The agent and frontend may remain on the host when the native bench moves to
QNX. The target environment should execute the system under investigation and
the components whose behavior depends on QNX.

## Level 1 — End-to-end laboratory

### Intended product

Level 1 should be a complete investigation loop on the host. It should not be a
standalone simulator that will later receive an unrelated agent.

An investigation should be able to:

1. receive a mechanic's case observations;
2. record their provenance and uncertainty without treating them as ground
   truth about the hidden vehicle state;
3. formulate rival mechanisms such as power loss, communication loss, or
   incomplete module recovery;
4. predict what each mechanism would look like in the virtual-ECU bench;
5. run controlled bench scenarios without exposing the injected mechanism to the
   investigator;
6. compare the simulated results with the real observations;
7. select a next observation or vehicle measurement that could discriminate the
   remaining explanations;
8. let a human review the proposed diagnostic plan; and
9. preserve the case file for replay and inspection.

The central separation is:

```text
vehicle evidence  !=  laboratory evidence  !=  laboratory oracle truth
```

The bench oracle knows what was injected and what happened inside the bench. It
is valid for evaluating the experiment. It is not evidence that the same
mechanism occurred in the vehicle.

### Example investigation

A mechanic reports intermittent loss of communication with a module during
startup. The initial record contains communication DTCs and a scanner report.
The investigator considers:

| Hypothesis | Bench experiment | Conditional result |
| --- | --- | --- |
| Module power drop | Restart a virtual ECU during a diagnostic exchange | Disconnection followed by a characteristic initialization sequence |
| Transport message loss | Introduce timeouts and dropped messages | Missing responses without module reinitialization |
| Recovery or persistence defect | Interrupt a persistent transition and run recovery | A state or evidence pattern different from a healthy restart |

The results can improve the next question, such as whether to measure power and
ground during the failure or capture additional timing information. They do not
diagnose the vehicle automatically.

### Actors and boundaries

| Actor | Responsibility | Authority boundary |
| --- | --- | --- |
| Mechanic | Provide observations, assess relevance, and perform safe vehicle measurements | Remains responsible for real-vehicle action |
| Investigator agent | Organize evidence, formulate hypotheses, predict outcomes, and request permitted experiments | Cannot write to a real ECU or present bench output as vehicle fact |
| Frontend | Enter a case, display reasoning and evidence, review plans, and export a report | Presentation and human review only |
| Harness | Prepare scenarios, inject bench faults, run experiments, and expose controlled observations | Operates virtual ECUs under the experiment contract |
| Witness | Reconstruct bench state, evaluate invariants, and package provenance | Does not fill gaps with unsupported facts |
| Oracle | Evaluate hidden bench truth for development and acceptance | Hidden from the investigator; never replaced by the LLM |

### Level 1 inputs

- mechanic-provided symptoms, DTCs, scanner reports, freeze frames, measurements,
  history, and previous test results;
- a virtual-ECU scenario and initial bench state;
- an observation policy defining what the investigator may request;
- allowed fault-injection mechanisms;
- witness invariants and oracle definitions; and
- a human review and safety boundary.

The exact schema is open. Real-vehicle observations must remain distinguishable
from generated bench inputs and hidden oracle labels.

### Level 1 outputs

The minimum output is a structured case file containing:

- source and provenance for every observation;
- competing hypotheses and their predicted signatures;
- bench experiments and parameters;
- observed bench results and oracle comparisons;
- comparison limits between the model and the real vehicle;
- recommended next observations or measurements for human review;
- hypotheses supported, refuted, or unresolved within the model;
- explicit uncertainty and abstentions;
- hashes and replay references for the artifacts; and
- a human-readable report, with PDF as a candidate presentation format.

The PDF is a view of the case file, not the source of truth. Original evidence
and structured records must remain available independently.

### Level 1 acceptance

Level 1 is complete when a recorded case can be replayed and the agent can:

- explain which observations came from the mechanic and which came from the
  bench;
- state at least two rival mechanisms and a prediction for each;
- select or request a bench experiment for an explicit discriminating reason;
- avoid seeing the hidden injection label;
- produce a bounded recommendation for the next human observation; and
- preserve a case file that a reviewer can inspect independently.

## Common evidence contract

The evidence contract is a prerequisite for every level. It must be designed
before Level 1 implementation so that moving the bench from host to QNX does not
silently change the meaning of an event.

Each event should preserve, at minimum:

- case, execution, and operation identities;
- event identity and sequence position;
- source category: vehicle, bench, witness, agent, or oracle;
- observation type and epistemic status;
- clock domain and timestamp semantics;
- correlation references, where known;
- reference to the original artifact;
- schema and contract version; and
- integrity metadata.

Real-vehicle evidence, simulated bench evidence, and oracle truth must remain
separate channels. They may be compared in a case file, but one must not be
silently promoted into another.

The contract should define what absence means. A missing vehicle log is not proof
that an event did not occur, and a bench-inferred event must not be serialized as
if it had been observed directly.

## Level 2 — Early ML experiment

Level 2 reuses the Level 1 laboratory and case-file contract. It does not create
a second diagnostic authority and does not make ML a prerequisite for QNX.

The experiment asks whether an optional learned signal contributes information
that explicit invariants, deterministic rules, and simpler reference methods do
not provide. The result may be that ML is retained, remains experimental, or is
discarded.

No dataset, model family, feature representation, training procedure, or
threshold is selected by this document. Those choices follow the first case and
bench campaigns. Any comparison must separate runs and failure mechanisms rather
than randomly split windows from the same execution.

ML output is a bounded observation for the investigator, not a diagnosis of the
vehicle. Its provenance, scope, uncertainty, and relationship to the bench must
be visible in the case file.

## Level 3 — QNX bench

Level 3 moves the native bench and required virtual-ECU components to QNX 8.0,
initially with QEMU as a possible target. The agent, frontend, and case-file
orchestration may remain on the host.

QNX should contribute evidence rather than merely serve as a label. The target
includes native processes, IPC, persistence behavior, interruptions, runtime
timing, user trace events, and kernel instrumentation. Host and QNX experiments
must preserve the common evidence contract and document semantic differences.

An early environment check should verify the toolchain, QNX APIs, tracing path,
persistence behavior, IPC requirements, and QEMU feasibility. This reduces
schedule risk; it is not an attempt to build the complete QNX level early.

Level 3 acceptance requires evidence that the same investigation question and
event meanings survive the platform transition. A successful compilation or
boot is not enough.

## Level 4 — Contrastive investigation

Level 4 gives the investigator real observations that are compatible with more
than one modeled mechanism. It must compare those observations with conditional
bench predictions and request measurements that can discriminate between them.

The agent should be able to say that a bench pattern is consistent with a power
drop but not proof of one, identify what additional vehicle observation would
separate it from message loss, and preserve unresolved alternatives when the
available evidence cannot decide.

Acceptance is about calibrated investigative behavior, not a confident label.

## Level 5 — Autonomous discovery

Level 5 evaluates autonomous exploration of the QNX bench for mechanisms absent
from development examples. The withheld mechanism must not be exposed directly
to the investigator.

The success condition is not that the agent announces a defect. It must produce
a reproducible bench experiment, preserve the evidence chain, and provide an
independent oracle or checker that confirms the bench defect. No discovery claim
transfers automatically to a real vehicle.

## Demonstration options

The final demonstration format remains open. Candidate formats include:

1. **Intermittent communication case:** mechanic observations lead to rival power
   and transport hypotheses, and the bench predicts different next measurements.
2. **Recovery contrast:** a module restart and an interrupted persistence
   transition produce distinguishable bench evidence.
3. **Human-in-the-loop investigation:** the agent proposes a measurement, the
   human supplies its result, and the next hypothesis set changes.
4. **ML decision point:** an optional signal is compared with explicit rules and
   the project visibly keeps or rejects it based on evidence.
5. **Discovery replay:** a withheld bench defect is found and replayed with an
   independent checker.

The choice should follow the first complete host case and the QNX feasibility
check. The demo must show the boundary between conditional simulation and real
vehicle evidence clearly.

## Open decisions

- the exact Level 1 mechanic-facing case;
- the common event and case-file schema;
- the initial virtual-ECU and transport boundary;
- C++17/QNX toolchain and adapter constraints;
- the Python agent and frontend interface;
- whether PDF export belongs in the first complete loop;
- the ML task and evaluation design; and
- the final demonstration format.

These are research decisions, not missing implementation details to be guessed
away. Each should be revisited when the preceding evidence exists.
