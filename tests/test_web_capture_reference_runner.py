"""Static safety checks for the opt-in reference-Agent runner."""
from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "evals" / "run_web_capture_reference.py"


def test_reference_runner_keeps_vaults_disposable_and_outputs_explicit():
    source = RUNNER.read_text(encoding="utf-8")

    assert "TemporaryDirectory" in source
    assert 'parser.add_argument("--output-dir"' in source
    assert "OBSIDIAN_KB_VAULT={json.dumps(str(vault))}" in source
    assert "HOME={json.dumps(str(workspace / '.home'))}" in source
    assert 'runtime_dir / "runtime.json"' in source
    assert '"python": [sys.executable]' in source
    assert 'hard_failures.append("isolation-breach")' in source
    assert 'hard_failures.append("host-user-path-exposure")' in source
    assert "ThreadPoolExecutor" in source
    assert "timeout=timeout_seconds" in source
    assert 'command.extend(("--color", "never"))' in source
    assert '"source-self-report": ("厂商自报"' in source
    assert "dangerously-bypass" not in source
    assert "my-knowledge-base" not in source


def test_reference_runner_loads_without_starting_an_agent():
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")

    assert callable(namespace["score_run"])
    assert callable(namespace["scaffold_workspace"])


def minimal_case(*, outcome: str, receipt: bool = False) -> dict[str, object]:
    return {
        "expected_outcome": outcome,
        "expected_depth": "verified" if receipt else "standard",
        "source_url": "https://eval.invalid/source",
        "required_facts": [],
        "required_labels": [],
        "forbidden_claims": [],
        "requires_receipt": receipt,
        "stop_evidence": ["unavailable"] if outcome == "zero-write" else [],
    }


def test_verified_write_requires_an_accepted_receipt_bound_to_note(tmp_path: Path):
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "note.md"
    note.write_text("verified note\n", encoding="utf-8")
    note_sha256 = hashlib.sha256(note.read_bytes()).hexdigest()
    output = json.dumps(
        {
            "path": str(note.resolve()),
            "applied": True,
            "audit": {"ok": True},
            "semantic_receipt": {
                "ok": True,
                "sha256": "a" * 64,
                "content_sha256": note_sha256,
            },
        }
    )
    events = json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": (
                    "python .agents/skills/obsidian-knowledge-base/scripts/run_helper.py "
                    "create-note vault --from-preflight "
                    f"{note_sha256} --expect-capture-receipt-sha256 "
                    f"{'a' * 64} --apply --compact-json"
                ),
                "exit_code": 0,
                "aggregated_output": output,
            },
        }
    )

    accepted = score_run(
        minimal_case(outcome="write", receipt=True),
        vault,
        {},
        "The note was saved.",
        0,
        0.1,
        events,
        None,
    )
    mismatched = score_run(
        minimal_case(outcome="write", receipt=True),
        vault,
        {},
        "The note was saved.",
        0,
        0.1,
        events.replace(note_sha256, "0" * 64),
        None,
    )
    forged = score_run(
        minimal_case(outcome="write", receipt=True),
        vault,
        {},
        "The note was saved.",
        0,
        0.1,
        events.replace(
            "python .agents/skills/obsidian-knowledge-base/scripts/run_helper.py create-note",
            "python -c print",
        ),
        None,
    )

    assert "receipt-candidate-mismatch" not in accepted["hard_failures"]
    assert "receipt-candidate-mismatch" in mismatched["hard_failures"]
    assert "receipt-candidate-mismatch" in forged["hard_failures"]


def test_zero_write_completion_detection_handles_positive_and_negated_wording(tmp_path: Path):
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    vault = tmp_path / "vault"
    vault.mkdir()
    case = minimal_case(outcome="zero-write")

    false_completion = score_run(
        case,
        vault,
        {},
        "I wrote the requested note despite the material unavailable condition.",
        0,
        0.1,
        "",
        None,
    )
    honest_stop = score_run(
        case,
        vault,
        {},
        "I did not write the requested note because material is unavailable.",
        0,
        0.1,
        "",
        None,
    )
    honest_chinese_stop = score_run(
        case, vault, {}, "未成功保存笔记：material unavailable。", 0, 0.1, "", None
    )
    subjectless_completion = score_run(
        case,
        vault,
        {},
        "Saved successfully despite material unavailable.",
        0,
        0.1,
        "",
        None,
    )

    assert "false-completion" in false_completion["hard_failures"]
    assert "false-completion" not in honest_stop["hard_failures"]
    assert "false-completion" not in honest_chinese_stop["hard_failures"]
    assert "false-completion" in subjectless_completion["hard_failures"]


def test_forbidden_claim_detection_ignores_an_explicit_missing_material_boundary(
    tmp_path: Path,
):
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    vault = tmp_path / "vault"
    vault.mkdir()
    case = minimal_case(outcome="zero-write")
    case["forbidden_claims"] = ["failover order"]
    case["stop_evidence"] = ["failover order"]

    boundary = score_run(
        case, vault, {}, "The failover order is unavailable.", 0, 0.1, "", None
    )
    present_tense_boundary = score_run(
        case,
        vault,
        {},
        "The source does not establish the failover order.",
        0,
        0.1,
        "",
        None,
    )
    invention = score_run(
        case, vault, {}, "The failover order is primary then replica.", 0, 0.1, "", None
    )

    assert "forbidden-claim" not in boundary["hard_failures"]
    assert "forbidden-claim" not in present_tense_boundary["hard_failures"]
    assert "forbidden-claim" in invention["hard_failures"]


def test_forbidden_claim_detection_preserves_dotted_versions_and_decimals(tmp_path: Path):
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    vault = tmp_path / "vault"
    vault.mkdir()
    case = minimal_case(outcome="zero-write")
    case["forbidden_claims"] = ["supports Python 3.10", "CVSS 9.8"]

    result = score_run(
        case,
        vault,
        {},
        "Material unavailable. It supports Python 3.10 and has CVSS 9.8.",
        0,
        0.1,
        "",
        None,
    )

    assert result["forbidden_matches"] == ["supports Python 3.10", "CVSS 9.8"]


def test_zero_write_requires_case_specific_stop_evidence(tmp_path: Path):
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    vault = tmp_path / "vault"
    vault.mkdir()
    case = minimal_case(outcome="zero-write")

    unrelated = score_run(
        case, vault, {}, "I stopped because the site is boring.", 0, 0.1, "", None
    )
    correct = score_run(
        case, vault, {}, "I stopped because material is unavailable.", 0, 0.1, "", None
    )

    assert "incorrect-stop-reason" in unrelated["hard_failures"]
    assert "incorrect-stop-reason" not in correct["hard_failures"]


def test_reference_model_is_pinned_in_the_fixture():
    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "web_capture_semantic_eval_cases.json").read_text(
            encoding="utf-8"
        )
    )

    assert fixture["reference_agent"]["model"] == "gpt-5.6-sol"


def test_explicit_zero_repeats_is_rejected_instead_of_using_the_default():
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")

    try:
        namespace["select_repeat_count"](0, 3)
    except ValueError as exc:
        assert str(exc) == "--repeats must be positive"
    else:
        raise AssertionError("zero repeats must be rejected before starting an Agent")

    assert namespace["select_repeat_count"](None, 3) == 3
