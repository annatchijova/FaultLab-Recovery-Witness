# Recovery Witness

**An automotive electronic-fault investigation laboratory.**

When a vehicle has an intermittent communication failure, a restart problem, a
power symptom, or a module that sometimes stops responding, the mechanic has
observations but not always a decisive explanation. Diagnostic trouble codes,
freeze frames, scanner reports, measurements, history, and previous test
results may support several competing hypotheses.

Recovery Witness is intended to help investigate those cases. A mechanic
provides observations from the real vehicle. An AI investigator organizes the
evidence, proposes rival explanations, predicts what each mechanism would look
like, and requests controlled experiments. A QNX-based laboratory runs those
experiments on virtual ECUs and reports which observations would distinguish the
hypotheses.

The laboratory does not know the internal state of the mechanic's vehicle. Its
simulation produces conditional predictions, not a diagnosis.

> QNX helps design discriminating tests. It does not manufacture evidence about
> the real vehicle.

## Project status

This repository is in the research and architecture phase. A first host-side
vertical slice now exists: a C++17 bench emits public observations separately
from a hidden oracle, a Python harness invokes the investigator, and a sealed
case file is produced while the system abstains from diagnosing the vehicle.
The full laboratory, OpenAI-backed investigator, QNX execution, and
demonstration format remain open.

The current research basis is in
[`docs/investigacion-inicial.md`](docs/investigacion-inicial.md). The proposed
construction sequence is in
[`docs/preliminary-levels.md`](docs/preliminary-levels.md). The earlier,
more ambitious recovery-auditor proposal is preserved as a deferred direction
in [`docs/deferred-real-vehicle-proposal.md`](docs/deferred-real-vehicle-proposal.md).

## The problem

Suppose a mechanic receives a vehicle with intermittent loss of communication
with a module. The scanner reports communication codes, and the customer says
the failure appears occasionally during startup.

Several explanations may fit the initial evidence:

| Hypothesis | Controlled laboratory experiment | What it may clarify |
| --- | --- | --- |
| Module power drop | Restart a virtual ECU during a diagnostic exchange | The pattern of disconnection, initialization, and recovery associated with a restart |
| Communication loss | Introduce transport timeouts and message loss | The pattern of missing communication without ECU reinitialization |
| Recovery or persistence defect | Interrupt a persistent transition and execute recovery | The signals that distinguish a healthy restart from incomplete recovery |

If the first experiment produces initialization after an interruption and the
second produces timeouts without initialization, the agent has a better question
to ask. It still has not proved which mechanism occurred in the real vehicle.

The next step may be to recommend checking power and ground under the failure
conditions, observing communication recovery, or capturing additional timing
data according to the vehicle and the mechanic's procedures. The mechanic
decides which measurements are relevant and safe. Those real observations can
feed the next investigation round.

## Intended architecture

```text
Mechanic and real vehicle
  symptoms, DTCs, scanner reports, freeze frames, measurements, history
                              |
                              v
AI investigator via OpenAI API
  evidence organization, rival hypotheses, predictions, test requests
                              |
                              v
QNX 8.0 experimental bench on QEMU
  virtual ECUs, fault injection, persistence, IPC, runtime traces
                              |
                              v
Forensic case file and diagnostic plan
  compatible hypotheses, refuted model mechanisms, recommended observations,
  uncertainty, provenance, and a possible PDF presentation
```

The experimental bench has its own oracle: it knows which mechanism was
injected and what actually happened inside the bench. That oracle evaluates the
experiment; it does not become evidence about the real vehicle.

## Why QNX belongs in the laboratory

Python could model abstract state transitions and generate hypothetical traces.
QNX adds a different experimental surface: native processes, inter-process
communication, persistence behavior, interruptions, runtime timing, user trace
events, and kernel instrumentation.

The QNX environment is therefore a test bench, not a digital twin of a vehicle
and not a claim that QEMU reproduces a physical CAN bus, electrical noise, power
behavior, or a commercial ECU. Validated hardware or models would be required
for those claims.

The proposed implementation split is:

- **C++17:** portable native bench, virtual ECU components, fault injector,
  witness, reconstruction, invariants, and platform adapters;
- **Python:** investigator agent, OpenAI API integration, experiment planning,
  case-file orchestration, and provisional frontend;
- **QNX 8.0:** target runtime for native bench components at the QNX level.

This is a proposed allocation. Toolchain compatibility and the exact boundary
between host and QNX components still need to be verified.

## Preliminary construction levels

The order follows construction dependencies and experimental risk:

1. **End-to-end laboratory:** a mechanic-facing case input, agent, host harness,
   witness, human review, reproducible evidence, and report artifact.
2. **Early ML experiment:** an optional signal evaluated against rules and
   simpler baselines, with a real option to discard it.
3. **QNX bench:** native experimental components and runtime traces on QNX 8.0.
4. **Contrastive investigation:** the agent compares real observations with
   predictions from rival mechanisms and requests measurements that discriminate
   between them.
5. **Autonomous discovery:** the agent explores the bench for previously
   withheld defects and produces a reproduction checked by an independent oracle.

The detailed preliminary plan and acceptance questions are in
[`docs/preliminary-levels.md`](docs/preliminary-levels.md).

## Run the host vertical slice

```bash
cmake -S . -B build
cmake --build build
PYTHONPATH=python python3 -m unittest discover -s tests -v
```

The `ecu_bench` executable can be called by
`recovery_witness.cli`. It writes public bench events to the harness and stores
the hidden development oracle in a separate file. The generated case file is
sealed with a versioned canonical serializer; the oracle is not passed to the
investigator.

## Scope and boundaries

- The initial domain is electronic, communication, power, restart, and module
  recovery behavior.
- The system does not diagnose arbitrary mechanical failures.
- QNX experiments produce predictions conditioned on the laboratory model.
- The system must distinguish real-vehicle evidence from simulated evidence.
- The mechanic remains responsible for selecting and safely performing vehicle
  measurements.
- The agent cannot write configuration to a real ECU.
- ML is optional and may be rejected if it does not add evidence beyond simpler
  methods.
- No production-safety, vehicle-safety, or real-device guarantee is claimed.

## Repository contents

```text
ECU/
├── LICENSE       # MIT license
├── CMakeLists.txt # C++17 build and smoke-test configuration
├── README.md     # project scope and current framing
├── docs/         # research, decisions, and preliminary design
├── src/          # C++17 host bench and future QNX adapters
├── python/       # host-side investigator and case-file primitives
├── tests/        # contract and determinism tests
├── skills/       # machine-learning research skills
└── .venv/        # local development environment, ignored by Git
```

The next design question is the exact Level 1 case: its actors, evidence
contract, investigation cycle, and proof that a requested experiment is
actually discriminating.

The first adversarial review of the host slice, including reproduced pre-fix
failures and their remediations, is documented in
docs/red-team-round-1.md.
