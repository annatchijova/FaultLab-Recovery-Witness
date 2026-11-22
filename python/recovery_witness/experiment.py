"""Plan public event observations against the finite host fixture catalogue."""

SIGNATURES = {
    "H1": ("diagnostic_request", "response_timeout", "module_restart", "module_initialized"),
    "H2": ("diagnostic_request", "response_timeout", "transport_recovered"),
    "H3": ("diagnostic_request", "persistence_interrupted", "recovery_started", "module_not_ready"),
}
QUESTIONS = {
    "H1": "Is module initialization recorded at the time of the communication loss?",
    "H2": "Does communication resume while the module's recorded uptime continues?",
    "H3": "Does the module report a ready state after the recorded recovery attempt?",
}
DEFAULT_QUESTION = "What initialization, communication and readiness records cover the same incident?"


def assess(events, case_id):
    """Choose each observation window before inspecting the next public event."""
    candidates = list(SIGNATURES)
    steps = []
    run_id = events[0].get("run_id") if events else None
    for position, event in enumerate(events, start=1):
        expected = {
            label: SIGNATURES[label][position - 1] if position <= len(SIGNATURES[label]) else None
            for label in candidates
        }
        if (event.get("case_id") != case_id or not isinstance(run_id, str) or not run_id
                or event.get("run_id") != run_id or event.get("sequence") != position
                or event.get("observed") is not True or event.get("clock_domain") != "simulated"
                or event.get("schema_version") != "event.v1"):
            candidates = []
            break
        candidates = [label for label in candidates if expected[label] == event["event_type"]]
        steps.append({"sequence": position, "expected_by_hypothesis": expected,
                      "observed_event": event["event_type"], "remaining": candidates.copy()})
        if not candidates:
            break
    match = next((label for label in candidates if len(events) == len(SIGNATURES[label])), None)
    probe = None
    if candidates and match is None:
        # Request the earliest unobserved position that separates live predictions.
        start = len(events)
        limit = min(len(SIGNATURES[label]) for label in candidates)
        for index in range(start, limit):
            predictions = {label: SIGNATURES[label][index] for label in candidates}
            if len(set(predictions.values())) > 1 or len(candidates) == 1:
                probe = {"sequence": index + 1, "predictions": predictions}
                break
    return {
        "next_bench_probe": probe,
        "schema_version": "host-signature-assessment.v1",
        "scope": "Ordered public events from one simulated host fixture",
        "requested_experiment": "Capture an ordered diagnostic exchange through restart, transport recovery or readiness.",
        "reason": "The three fixtures share a request but predict different recovery sequences.",
        "steps": steps,
        "matched_hypothesis": match,
        "candidate_prefixes": candidates,
    }, QUESTIONS.get(match, DEFAULT_QUESTION)
