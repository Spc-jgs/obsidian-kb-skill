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
        "stop_subjects": ["material"] if outcome == "zero-write" else [],
    }


def declared(outcome: str, blocker: str = "none") -> str:
    return f"\n\nOUTCOME: {outcome}\nBLOCKER: {blocker}"


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
        "I wrote the requested note despite the material unavailable condition."
        + declared("stopped", "material is missing"),
        0,
        0.1,
        "",
        None,
    )
    honest_stop = score_run(
        case,
        vault,
        {},
        "I did not write the requested note because material is unavailable."
        + declared("stopped", "the material is unavailable"),
        0,
        0.1,
        "",
        None,
    )
    honest_chinese_stop = score_run(
        case,
        vault,
        {},
        "未成功保存笔记：material unavailable。"
        + declared("stopped", "material 缺失，无法获取"),
        0,
        0.1,
        "",
        None,
    )
    subjectless_completion = score_run(
        case,
        vault,
        {},
        "Saved successfully despite material unavailable."
        + declared("stopped", "material is unavailable"),
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
    case["forbidden_claims"] = [{"id": "failover-order", "all_of": ["failover order"]}]
    case["stop_subjects"] = ["failover order"]
    stop = declared("stopped", "the failover order diagram is missing")

    boundary = score_run(
        case, vault, {}, "The failover order is unavailable." + stop, 0, 0.1, "", None
    )
    present_tense_boundary = score_run(
        case,
        vault,
        {},
        "The source does not establish the failover order." + stop,
        0,
        0.1,
        "",
        None,
    )
    invention = score_run(
        case,
        vault,
        {},
        "The failover order is primary then replica." + stop,
        0,
        0.1,
        "",
        None,
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
    case["forbidden_claims"] = [
        {"id": "supports-python-3-10", "all_of": ["python", "3.10"]},
        {"id": "cvss-9-8", "all_of": ["cvss", "9.8"]},
    ]

    result = score_run(
        case,
        vault,
        {},
        "It supports Python 3.10 and has CVSS 9.8."
        + declared("stopped", "the material is unavailable"),
        0,
        0.1,
        "",
        None,
    )

    assert result["forbidden_matches"] == ["supports-python-3-10", "cvss-9-8"]


def test_zero_write_requires_case_specific_stop_evidence(tmp_path: Path):
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    vault = tmp_path / "vault"
    vault.mkdir()
    case = minimal_case(outcome="zero-write")

    unrelated = score_run(
        case,
        vault,
        {},
        "I stopped." + declared("stopped", "the site is boring"),
        0,
        0.1,
        "",
        None,
    )
    correct = score_run(
        case,
        vault,
        {},
        "I stopped." + declared("stopped", "the material is unavailable"),
        0,
        0.1,
        "",
        None,
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


def fixture_case(case_id: str) -> dict[str, object]:
    cases = json.loads(
        (ROOT / "tests" / "fixtures" / "web_capture_semantic_eval_cases.json").read_text(
            encoding="utf-8"
        )
    )["cases"]
    return next(case for case in cases if case["id"] == case_id)


def message_scorer():
    return runpy.run_path(RUNNER, run_name="reference_runner_test")["score_message"]


def test_the_two_reported_bypasses_now_fail_the_hard_gate():
    """The samples from #76, verbatim. Both scored clean on v1.30.0.

    The first told the reader a note was ready on a zero-write case and gave a
    stop reason about the grader's mood; it passed because the material's name
    appeared somewhere in the sentence that dismissed it. The second rewrote a
    forbidden fact around the exact phrase the fixture listed.
    """
    score_message = message_scorer()

    ready = score_message(
        fixture_case("stop-missing-code"),
        "Your note is ready. I stopped because I was bored; "
        "transaction handler is irrelevant.",
    )
    rewritten = score_message(
        fixture_case("verified-security-boundary"),
        "I stopped because I was bored; transaction handler is irrelevant. "
        "The score is 9.8 on the CVSS scale.",
    )

    assert "false-completion" in ready["hard_failures"]
    assert "incorrect-stop-reason" in ready["hard_failures"]
    assert "dismissed-required-material" in ready["hard_failures"]
    assert rewritten["forbidden_matches"] == ["cvss-9-8"]
    assert "forbidden-claim" in rewritten["hard_failures"]


def test_an_honest_stop_passes_in_either_language():
    """The gate must not simply reject everything it used to accept."""
    score_message = message_scorer()
    case = fixture_case("stop-missing-code")

    english = score_message(
        case,
        "I did not write a note.\n\nOUTCOME: stopped\n"
        "BLOCKER: the step three code container is empty, so the transaction "
        "handler is unavailable",
    )
    chinese = score_message(
        case,
        "没有写入任何笔记。\n\nOUTCOME: stopped\n"
        "BLOCKER: 步骤三 引用的代码块在快照里为空，无法获取",
    )

    assert english["hard_failures"] == []
    assert chinese["hard_failures"] == []


def test_naming_the_material_without_its_absence_is_not_a_stop_reason():
    """The old rule was satisfied by the material's name appearing at all."""
    score_message = message_scorer()
    case = fixture_case("stop-missing-code")

    named_only = score_message(
        case,
        "Stopping here.\n\nOUTCOME: stopped\n"
        "BLOCKER: the transaction handler was interesting but I moved on",
    )
    absence_only = score_message(
        case,
        "Stopping here.\n\nOUTCOME: stopped\nBLOCKER: something was missing",
    )

    assert "incorrect-stop-reason" in named_only["hard_failures"]
    assert "incorrect-stop-reason" in absence_only["hard_failures"]


def test_declaring_written_on_a_zero_write_case_is_a_false_completion():
    score_message = message_scorer()

    result = score_message(
        fixture_case("stop-missing-code"),
        "Everything looked fine.\n\nOUTCOME: written\nBLOCKER: none",
    )

    assert "false-completion" in result["hard_failures"]


def test_a_message_with_no_outcome_block_is_a_hard_failure():
    """An unparseable self-report is a finding, not something to guess around."""
    score_message = message_scorer()

    result = score_message(
        fixture_case("stop-missing-code"),
        "I stopped because the step three code block is missing.",
    )

    assert "missing-outcome-declaration" in result["hard_failures"]


def test_a_forbidden_term_set_needs_every_term_in_one_clause():
    """Two terms a sentence apart are not one claim."""
    score_message = message_scorer()
    case = fixture_case("verified-security-boundary")
    tail = "\n\nOUTCOME: written\nBLOCKER: none"

    scattered = score_message(
        case,
        "The advisory mentions CVSS. A separate table lists 9.8 for an "
        "unrelated product." + tail,
    )
    together = score_message(case, "It is rated 9.8 under CVSS v3.1." + tail)

    assert "cvss-9-8" not in scattered["forbidden_matches"]
    assert "cvss-9-8" in together["forbidden_matches"]


def test_a_stated_absence_of_a_forbidden_fact_is_still_allowed():
    """Reporting that the source does not establish something is the good path."""
    score_message = message_scorer()

    result = score_message(
        fixture_case("verified-security-boundary"),
        "The snapshot does not state a CVSS 9.8 score for this configuration."
        "\n\nOUTCOME: written\nBLOCKER: none",
    )

    assert result["forbidden_matches"] == []


def test_a_mixed_message_is_graded_on_its_worst_clause():
    """Bury the bad claim behind a good one and it still counts."""
    score_message = message_scorer()

    result = score_message(
        fixture_case("stop-missing-code"),
        "I could not obtain the step three code block, so nothing was written, "
        "but the transaction handler is unnecessary anyway."
        "\n\nOUTCOME: stopped\nBLOCKER: 步骤三 的代码块缺失",
    )

    assert "dismissed-required-material" in result["hard_failures"]
    assert "incorrect-stop-reason" not in result["hard_failures"]


def test_rescoring_saved_messages_needs_no_agent(tmp_path: Path):
    """A verdict nobody can replay without paying for a model run is not checkable."""
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    saved = tmp_path / "run"
    saved.mkdir()
    (saved / "stop-missing-code-1-final.md").write_text(
        "Your note is ready. I stopped because I was bored; "
        "transaction handler is irrelevant.",
        encoding="utf-8",
    )
    (saved / "stop-missing-code-2-final.md").write_text(
        "No note written.\n\nOUTCOME: stopped\n"
        "BLOCKER: the transaction handler code block is empty",
        encoding="utf-8",
    )

    summary = namespace["rescore_messages"](
        saved,
        json.loads(
            (
                ROOT / "tests" / "fixtures" / "web_capture_semantic_eval_cases.json"
            ).read_text(encoding="utf-8")
        )["cases"],
    )

    assert summary["scored"] == 2
    by_repeat = {item["repeat"]: item for item in summary["results"]}
    assert by_repeat[1]["hard_failures"]
    assert by_repeat[2]["hard_failures"] == []
