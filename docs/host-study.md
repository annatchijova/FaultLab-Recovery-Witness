# Host study and human review

Build and run the entire host catalogue from the repository root. The output
directory must be new. The example observation is synthetic.

```sh
cmake -S . -B build
cmake --build build
python3 tools/run_host_study.py --bench build/ecu_bench --case-id example-001 \
  --mechanic-observation "Intermittent startup communication loss" --output /tmp/ecu-example-001
```

Inspect the three text reports under `study/`. Each is rendered from a verified
case. Each case preserves the reported symptom, public bench observations,
rival predictions and the next proposed human observation. The event sequence
and run identity must agree before a signature matches. A partial prefix can
retain candidate hypotheses without supporting a complete signature.
The bench assessment concerns the fixture alone. Each vehicle decision abstains.

The runner schedules all three controlled scenarios for comparison. Its ordered
predictions are fixed by the catalogue. It does not choose a fault based on
free-text interpretation or adapt the running native process.
The analyst reviews the proposed observation before taking any vehicle action.

The private directory contains the three development oracles and the aggregate
comparison. Keep that directory outside investigator inputs. The evaluation
counts exact signature matches, compares with a constant predictor and rotates
labels as a negative control. There is one independent template per class.
Repeating runs or changing identifiers cannot establish a useful ML holdout.
A future experiment needs independently generated cases for each mechanism,
including ambiguous observations and variations in event timing and availability.

To check repeatability or inspect a previously recorded case:

```sh
python3 tools/check_host_replay.py --bench build/ecu_bench
python3 tools/verify_case.py /tmp/ecu-example-001/study/run-1.json
python3 tools/review_case.py /tmp/ecu-example-001/study/run-1.json
```
