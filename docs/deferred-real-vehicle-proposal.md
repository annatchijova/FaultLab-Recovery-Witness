# Deferred Proposal — Direct Recovery Witness for Real Vehicles

**Status:** Rejected for the current hackathon; retained as a future research direction

This document preserves an earlier and more ambitious direction: treating
Recovery Witness as a system that could directly establish the recovery state of
a real ECU or vehicle after an interrupted operation.

The idea is valuable, but it is not a realistic commitment for the current
hackathon. The proposal is deferred because its claims would depend on logistics,
hardware, validated models, and safety controls that are not currently available.

## The earlier proposal

The earlier direction combined:

- a simulated or instrumented ECU;
- persistent transitions, recovery, and fault injection;
- QNX 8.0 runtime tracing;
- an AI investigator that reconstructed what happened;
- optional ML for patterns not covered by explicit rules; and
- a forensic report intended to support a recovery conclusion.

In its strongest form, the system could have been interpreted as an auditor of a
real vehicle or ECU. That interpretation is too strong for a generic virtual ECU
running on QEMU and too risky without validated hardware and procedures.

## Why it is rejected for this hackathon

### Logistics

- There is no guaranteed access to a representative fleet of vehicles, ECUs,
  diagnostic interfaces, or repeatable failure cases.
- Real cases arrive with incomplete, vehicle-specific evidence and cannot be
  replayed as controlled experiments without cooperation from the mechanic and
  access to the vehicle.
- A useful validation campaign would require repeated tests across modules,
  vehicle configurations, operating conditions, and fault mechanisms.
- The hackathon timeline does not support establishing that operational campaign
  while also building the agent, witness, harness, QNX bench, and evidence
  workflow.

### Hardware and modeling

- QEMU does not automatically model electrical power drops, physical CAN
  behavior, transceiver faults, wiring, electromagnetic effects, or the timing
  of a commercial ECU.
- A virtual ECU designed for this project is an experimental model, not a digital
  twin of the mechanic's vehicle.
- Direct experiments would require appropriate CAN interfaces, power control,
  measurement equipment, ECU fixtures, validated models, and a safe way to
  inject faults.
- Without that boundary, an experiment can demonstrate what the model does but
  cannot establish what the vehicle did.

### Critical-system and safety boundaries

- Writing configuration or inducing faults on a production vehicle or ECU can
  create safety, liability, and recovery risks.
- A model-generated hypothesis must not authorize an unsafe vehicle operation or
  be presented as a confirmed diagnosis.
- Real-vehicle measurements require the mechanic's judgment, vehicle-specific
  procedures, and appropriate safeguards.
- Claims about production safety, roadworthiness, or reliable recovery would
  require validation outside a hackathon prototype.

### Scope and evidence

- The project would otherwise combine diagnosis, ECU modeling, QNX porting, ML
  evaluation, agent design, evidence custody, and report generation into one
  unbounded claim.
- The evidence needed to validate the strongest claim is not the same as the
  evidence produced by a simulated recovery scenario.
- A successful simulation, restart, or agent explanation cannot bridge that gap
  without an independently validated correspondence between model and vehicle.

## Decision

For the current hackathon, Recovery Witness will be framed as an automotive
electronic-fault investigation laboratory:

```text
real-vehicle observations
          |
          v
AI-generated hypotheses and predicted distinctions
          |
          v
controlled QNX experiments on virtual ECUs
          |
          v
conditional predictions and recommended observations
```

The laboratory helps design discriminating tests. It does not claim to know the
hidden state of the real vehicle and does not replace the mechanic's judgment.

This preserves the useful core of the earlier proposal: reproducible faults,
runtime evidence, abduction, invariants, and QNX as an experimental environment.
It narrows the claim to what the available system can actually support.

## What remains reusable

- QNX process, IPC, persistence, and tracing experiments;
- virtual ECU and fault-injection models;
- a witness that reconstructs the bench state;
- an independent bench oracle;
- a case file that separates observation, hypothesis, experiment, and conclusion;
- an AI investigator that chooses the next useful test; and
- an optional ML experiment that can be rejected if it adds no value.

## Revisit conditions

The deferred proposal may be reconsidered only when the project has, at minimum:

- access to appropriate vehicles or ECU fixtures;
- validated models or measurement evidence connecting the bench to the target
  hardware;
- a documented fault-injection and recovery safety procedure;
- vehicle-specific diagnostic and operational boundaries;
- a reproducible acquisition and evidence-custody workflow; and
- an evaluation plan that keeps simulation evidence separate from real-vehicle
  conclusions.

Until those conditions exist, calling the system a direct real-vehicle recovery
auditor would overstate what the evidence can support.
