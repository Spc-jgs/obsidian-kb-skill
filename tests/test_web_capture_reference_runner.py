"""Static safety checks for the opt-in reference-Agent runner."""
from __future__ import annotations

import hashlib
import json
import re
import runpy
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "evals" / "run_web_capture_reference.py"


def unescaped(rendered: str) -> str:
    """Undo JSON's backslash doubling before looking for a path.

    A backend may embed paths with `json.dumps`, which is identity for a POSIX
    path and doubles every separator in a Windows one. Searching the raw text
    for `C:\\Users\\...` then finds nothing, and the isolation assertion fails
    on Windows while passing everywhere its author ran it — the assertion was
    about the path being named, never about how it was quoted.
    """
    return rendered.replace("\\\\", "\\")


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


def test_every_backend_points_the_agent_at_the_disposable_workspace(tmp_path: Path):
    """The isolation claim covers each product, not whichever one was first.

    The assertions above read source text belonging to one backend, and a
    second product's invocation could contradict every one of them while they
    stayed green — the shape row 17 of the consistency inventory records. This
    asks each backend what it will actually hand the Agent.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    workspace = tmp_path / "workspace"
    vault = workspace / "vault"
    cache = workspace / ".preflight-cache"

    for name, backend in namespace["AGENT_BACKENDS"].items():
        environment = backend.environment(workspace, vault, cache)
        command = backend.command(
            workspace=workspace,
            final_path=tmp_path / "final.md",
            material=None,
            model=backend.default_model,
            prompt="prompt",
        )
        rendered = unescaped(" ".join(command) + " " + json.dumps(environment))

        assert str(vault) in rendered, name
        assert str(workspace / ".home") in rendered, name
        # Nothing may name the real home directory: that is where the
        # operator's global Skills live, one of which is an installed copy of
        # the Skill being measured.
        assert str(Path.home() / ".agents") not in rendered, name

        if backend.inherits_operator_environment:
            # The product applies the disposable HOME to the tools it spawns
            # rather than to itself, so the command has to carry it — the
            # environment legitimately still holds the operator's.
            assert str(workspace / ".home") in unescaped(" ".join(command)), name
        else:
            # No such mechanism, so the product runs under the disposable HOME
            # itself and its own environment is the only place that can say so.
            assert environment["HOME"] == str(workspace / ".home"), name
            assert environment["OBSIDIAN_KB_VAULT"] == str(vault), name
            assert environment["TMPDIR"] == str(workspace / ".tmp"), name


def test_no_backend_lets_the_agent_reach_the_network_for_source_material():
    """The snapshot in the prompt is the acquisition result, by construction.

    A run that fetched the `.invalid` URL — or searched for the product it
    describes — would be graded on material this eval never controlled, and
    the forbidden-claim rules would be checking the wrong text.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    workspace = Path("/tmp/workspace")

    for name, backend in namespace["AGENT_BACKENDS"].items():
        rendered = " ".join(
            backend.command(
                workspace=workspace,
                final_path=Path("/tmp/final.md"),
                material=None,
                model=backend.default_model,
                prompt="prompt",
            )
        )
        assert "web_search=false" in rendered or "--disable-web-search" in rendered, name


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


def apply_command(note_sha256: str) -> str:
    return (
        "python .agents/skills/obsidian-knowledge-base/scripts/run_helper.py "
        f"create-note vault --from-preflight {note_sha256} "
        f"--expect-capture-receipt-sha256 {'a' * 64} --apply --compact-json"
    )


def codex_events(command: str, output: str) -> str:
    return json.dumps(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": command,
                "exit_code": 0,
                "aggregated_output": output,
            },
        }
    )


def grok_events(command: str, output: str) -> str:
    """One finished tool call in the shape grok streams it.

    `output_for_prompt` really does carry grok's own `exit: 0` line ahead of
    the command's stdout, so the payload here is prefixed the way a live run
    prefixes it — a fixture that handed the runner clean JSON would pass while
    every real receipt failed to parse.
    """
    return json.dumps(
        {
            "type": "tool_call_update",
            "toolCallId": "call-0",
            "status": "completed",
            "rawOutput": {
                "type": "Bash",
                "command": command,
                "exit_code": 0,
                "output_for_prompt": f"exit: 0\n{output}",
                "truncated": False,
            },
        }
    )


@pytest.mark.parametrize("agent,build", (("codex", codex_events), ("grok", grok_events)))
def test_verified_write_requires_an_accepted_receipt_bound_to_note(
    tmp_path: Path, agent: str, build
):
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    backend = namespace["AGENT_BACKENDS"][agent]
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
    events = build(apply_command(note_sha256), output)

    def graded(stream: str) -> dict:
        return score_run(
            minimal_case(outcome="write", receipt=True),
            vault,
            {},
            "The note was saved.",
            0,
            0.1,
            stream,
            None,
            backend.executions(stream),
            None,
        )

    accepted = graded(events)
    mismatched = graded(events.replace(note_sha256, "0" * 64))
    forged = graded(
        events.replace(
            "python .agents/skills/obsidian-knowledge-base/scripts/run_helper.py create-note",
            "python -c print",
        )
    )

    assert "receipt-candidate-mismatch" not in accepted["hard_failures"]
    assert "receipt-candidate-mismatch" in mismatched["hard_failures"]
    assert "receipt-candidate-mismatch" in forged["hard_failures"]


def test_a_grok_command_still_running_does_not_prove_a_receipt(tmp_path: Path):
    """An in-progress update repeats the command with partial output.

    Grok emits the same call several times as it runs, and the earlier events
    already carry the command line. Counting them would let a receipt be read
    off a command that had not finished — and, since the exit code is present
    from the start, it would look exactly like success.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    backend = namespace["AGENT_BACKENDS"]["grok"]
    finished = grok_events("echo hi", "{}")
    running = finished.replace('"status": "completed"', '"status": "in_progress"')

    assert len(backend.executions(finished)) == 1
    assert backend.executions(running) == []


def test_grok_receipt_parsing_ignores_the_agents_own_status_line():
    """The payload proving a receipt must be the helper's, not the harness's.

    Grok prefixes captured output with `exit: 0`. Feeding that to `json.loads`
    fails, so without stripping it every verified case would report
    `receipt-candidate-mismatch` no matter what the helper actually returned.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    helper_json_output = namespace["helper_json_output"]

    assert json.loads(helper_json_output('exit: 0\n{"applied": true}')) == {
        "applied": True
    }
    assert json.loads(helper_json_output('{"applied": true}')) == {"applied": True}
    assert helper_json_output("exit: 1\ncommand not found") == ""


def test_the_final_message_is_the_last_turn_and_not_the_whole_run():
    """Narration before a tool call is not part of the closing message.

    Codex writes only the final message to `-o`. Grok streams every assistant
    delta, so concatenating them would put text the other backend never saw in
    front of the forbidden-claim and dismissal rules — the same run would be
    graded differently for having used a different product.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    backend = namespace["AGENT_BACKENDS"]["grok"]
    stream = "\n".join(
        (
            json.dumps({"type": "text", "data": "I will invent nothing. "}),
            grok_events("echo hi", "{}"),
            json.dumps({"type": "text", "data": "OUTCOME: written"}),
        )
    )

    assert backend.final_message(stream, Path("/nonexistent")) == "OUTCOME: written"


def test_no_backend_copies_anything_but_a_credential_out_of_the_real_home():
    """Isolation is the redirected HOME; the credential is the one exception.

    On a developer machine `~/.agents/skills/obsidian-knowledge-base` is a
    symlink to an installed copy of the Skill under test and `~/.grok/config.toml`
    enables plugins, so copying a directory — or a config file — would let the
    operator's setup into the measurement. Only named credential files may
    cross, and the list stays short enough to read.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")

    for backend in namespace["AGENT_BACKENDS"].values():
        assert all(name.endswith(".json") for name in backend.credential_files)
        assert "config" not in " ".join(backend.credential_files)
        assert len(backend.credential_files) <= 2


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
        [],
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
        [],
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
        [],
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
        [],
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
        case, vault, {}, "The failover order is unavailable." + stop, 0, 0.1, "", None, [], None
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
        [],
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
        [],
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
        [],
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
        [],
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
        [],
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


CHINESE_CLAIM = [{"id": "supports-python-3-10", "all_of": ["python", "3.10"]}]


def test_a_chinese_note_recording_what_a_source_excludes_is_not_asserting_it():
    """`不支持 X` states the opposite of `supports X` and was graded as it.

    The negation branch listed four write-outcome verbs — 保存, 沉淀, 写入,
    创建 — which reads like Chinese coverage and is a list of four. Every note
    the fixture requires to record `不支持 Python 3.10` as a required fact was
    therefore also reported as asserting the forbidden claim, and the gate
    stopped the run on it. Both orders occur in one real note.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    forbidden_assertions = namespace["forbidden_assertions"]

    assert forbidden_assertions(
        "Quartz Runner 2.4.1 不支持 Python 3.10。", CHINESE_CLAIM
    ) == []
    assert forbidden_assertions(
        "Python 3.10 不被 Quartz Runner 2.4.1 支持。", CHINESE_CLAIM
    ) == []
    assert forbidden_assertions("明确不适用：Python 3.10。", CHINESE_CLAIM) == []


def test_the_forbidden_claim_gate_still_bites_a_genuine_chinese_assertion():
    """The hard negative for the fix above.

    Broadening negation is only safe if a note that really does claim the
    forbidden thing is still caught, in the same language and the same
    sentence shapes — otherwise the repair is indistinguishable from deleting
    the rule.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    forbidden_assertions = namespace["forbidden_assertions"]

    assert forbidden_assertions(
        "Quartz Runner 2.4.1 支持 Python 3.10。", CHINESE_CLAIM
    ) == ["supports-python-3-10"]
    # A negation earlier in the sentence must not license the claim after the
    # contrastive conjunction, which is exactly where a rationalisation goes.
    assert forbidden_assertions(
        "文档不长，但 2.4.1 支持 Python 3.10。", CHINESE_CLAIM
    ) == ["supports-python-3-10"]


def test_two_chinese_statements_joined_by_a_comma_are_not_one_claim():
    """`，` chains independent clauses where English would start a sentence.

    Measured, not assumed: a real note wrote `原文把 2.4.1 和 Python 3.12
    绑定，并单独排除 3.10`, and the two terms of the forbidden claim landed in
    one clause from two statements that each say something else. Nothing in
    that sentence asserts the claim, and the run was stopped by it.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    forbidden_assertions = namespace["forbidden_assertions"]

    assert forbidden_assertions(
        "原文把 2.4.1 和 Python 3.12 绑定，并单独排除 3.10。", CHINESE_CLAIM
    ) == []
    # An English comma is deliberately not a boundary: it joins phrases far
    # more often than it joins independent clauses, and splitting there would
    # let a claim be spread across two fragments of one sentence. The terms
    # here straddle the comma on purpose — the first version of this assertion
    # put both on one side, so it passed whether or not `,` was a boundary and
    # proved nothing about the asymmetry it was written to defend.
    assert forbidden_assertions(
        "The runner supports Python, including 3.10.", CHINESE_CLAIM
    ) == ["supports-python-3-10"]


def test_the_note_that_stopped_the_first_grok_run_now_grades_clean():
    """The whole note, not the sentences remembered from reading it.

    The three shapes above were found by reading a graded artifact; a fixture
    built from that reading can miss whichever fourth shape was skimmed. This
    replays the file itself.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    forbidden_assertions = namespace["forbidden_assertions"]
    note = Path(__file__).with_name("fixtures") / "grok_chinese_capture_note.md"

    assert forbidden_assertions(note.read_text(encoding="utf-8"), CHINESE_CLAIM) == []


def test_a_backend_without_attachments_is_told_where_the_material_is():
    """"The attached image" points at nothing when nothing was attached.

    The grok backend accepted the material argument and never used it, so the
    one case whose prompt says the diagram is key evidence ran without ever
    being shown one. It still scored well, because that case's required facts
    all happen to be recoverable from the text — the run looked fine and the
    instruction had not been carried out.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    prompt_for = namespace["prompt_for"]

    def case_with(**extra: object) -> dict[str, object]:
        case = minimal_case(outcome="write")
        case.update({"prompt": "沉淀这份说明。", "source_markdown": "# source"})
        case.update(extra)
        return case

    with_material = case_with(material_asset="docs/assets/diagram.webp")
    attached = prompt_for(with_material, None)
    by_path = prompt_for(with_material, "source-assets/diagram.webp")

    assert "attached image" in attached
    assert "source-assets/diagram.webp" in by_path
    assert "attached image" not in by_path
    # A case with no material must gain neither sentence, whichever backend.
    assert "material source asset" not in prompt_for(case_with(), None)


def test_every_backend_either_attaches_the_material_or_is_told_to_name_it():
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")

    for name, backend in namespace["AGENT_BACKENDS"].items():
        rendered = " ".join(
            backend.command(
                workspace=Path("/tmp/workspace"),
                final_path=Path("/tmp/final.md"),
                material=Path("/tmp/workspace/source-assets/diagram.webp"),
                model=backend.default_model,
                prompt="prompt",
            )
        )
        if backend.attaches_material:
            assert "diagram.webp" in rendered, name
        else:
            # It must not silently drop it: the path goes in the prompt, which
            # `run_case` builds from `attaches_material`, so the flag is the
            # whole contract and a backend claiming to attach must really do it.
            assert "diagram.webp" not in rendered, name


def test_a_run_says_when_the_isolation_check_had_nothing_to_compare(tmp_path: Path):
    """A guard with no subject must not read as a guard that passed.

    `isolation-breach` searches the transcript for the operator's own Vault
    path. That path comes from `OBSIDIAN_KB_VAULT`, which is simply unset on
    some machines — including the one this eval was run on — and the check then
    cannot fire at all. Zero hard failures would otherwise be quoted as proof
    of isolation the run never tested.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    vault = tmp_path / "vault"
    vault.mkdir()

    def graded(forbidden: str | None) -> dict:
        return score_run(
            minimal_case(outcome="zero-write"),
            vault,
            {},
            "I stopped." + declared("stopped", "the material is unavailable"),
            0,
            0.1,
            "",
            forbidden,
            [],
            None,
        )

    assert graded(None)["isolation_check"] == "no-operator-vault-to-compare"
    assert graded("/Users/someone/Vault")["isolation_check"] == "checked"


def test_a_windows_path_is_still_found_after_json_doubled_its_separators():
    """The isolation assertion is about naming a path, not about quoting it.

    Codex embeds paths with `json.dumps`, which is identity on POSIX and
    doubles every separator on Windows. The assertion that the disposable
    workspace is named therefore passed on the author's machine and failed on
    Windows CI, against a command that named the path correctly. Written with
    literal strings so it checks the same thing on every platform.
    """
    windows = r"C:\Users\runner\Temp\workspace\vault"
    embedded = json.dumps(windows)

    assert windows not in embedded
    assert windows in unescaped(embedded)
    # POSIX paths are untouched, so the repair cannot mask a real miss there.
    assert unescaped('"/tmp/workspace/vault"') == '"/tmp/workspace/vault"'


FIXTURE = ROOT / "tests" / "fixtures" / "web_capture_semantic_eval_cases.json"


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def case_named(case_id: str) -> dict:
    return next(case for case in fixture()["cases"] if case["id"] == case_id)


def test_a_case_that_says_the_image_is_evidence_asks_for_something_only_the_image_has():
    """Otherwise the case can score full marks without opening the image.

    `standard-material-diagram` is the one case whose prompt says 配图是关键
    证据，必须读图, and every one of its original five facts appears in its own
    `source_markdown` — while that source states outright that the text does
    not specify what the diagram adds. It was an evaluation asset that could
    not fail at the thing it exists to test, which is #117's shape.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    fact_forms = namespace["fact_forms"]
    case = case_named("standard-material-diagram")
    source = case["source_markdown"].casefold()

    recoverable = [
        fact
        for fact in case["required_facts"]
        if any(form.casefold() in source for form in fact_forms(fact))
    ]
    assert len(recoverable) < len(case["required_facts"]), (
        "every required fact is in the text, so the image is never needed"
    )


def test_every_alternative_fact_form_records_where_it_was_observed():
    """A vocabulary grows from forms that were seen, not forms that sound right.

    #75 settled this for the dependency markers and #115 paid for the opposite:
    a heading vocabulary two characters short reported three present sections
    as missing. An unrecorded form here has no way to be checked, and the next
    reader cannot tell a measurement from a guess.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    fact_forms = namespace["fact_forms"]
    data = fixture()
    provenance = data["fact_form_provenance"]

    for case in data["cases"]:
        for fact in case["required_facts"]:
            forms = fact_forms(fact)
            for alternative in forms[1:]:
                assert alternative in provenance, (
                    f"{case['id']}: {alternative} has no recorded provenance"
                )
                assert provenance[alternative].strip(), alternative


def test_the_same_knowledge_scores_the_same_in_either_language():
    """The metric must measure the fact, not which language echoed the source.

    Measured on the 2026-08-17 baseline: two notes for `standard-material-diagram`
    each recorded all five facts in Chinese — 只读 x9, 检索 x7, 写入 x12,
    用户意图 x3, 预检 x7 in one of them — and scored 5/5 against 1/5. The whole
    difference was that one happened to echo each English term once.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    fact_present = namespace["fact_present"]
    facts = case_named("standard-qualified-benchmark")["required_facts"]

    english = "hardware, sample, warm-up, latency and error rate are all absent; 40% at 1000"
    chinese = "原文未提供硬件、样本量、预热策略、延迟分位数与错误率；1000 并发下快 40%"

    assert [f for f in facts if fact_present(english, f)] == facts
    assert [f for f in facts if fact_present(chinese, f)] == facts


def test_a_fact_absent_in_both_languages_is_still_a_miss():
    """The hard negative: accepting more forms must not accept everything."""
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    fact_present = namespace["fact_present"]
    facts = case_named("standard-qualified-benchmark")["required_facts"]

    silent = "原文比较了两个客户端的相对性能，未给出任何方法细节。"
    assert [f for f in facts if fact_present(silent, f)] == []


def test_naming_the_image_in_a_listing_is_not_inspecting_it(tmp_path: Path):
    """A colour fact cannot tell reading the diagram from guessing it.

    "The left path is blue" is both a finding and a plausible guess, so the
    note can never settle whether the asset was opened. The transcript can.
    Measured on the 2026-08-17 baseline: every run listed the workspace and
    printed the filename, which is why a listing must not count.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    backend = namespace["AGENT_BACKENDS"]["grok"]
    material = tmp_path / "source-assets" / "diagram.webp"

    listed = json.dumps({
        "type": "tool_call",
        "toolName": "run_terminal_command",
        "rawInput": {"command": "ls source-assets", "description": "list assets"},
    }) + "\n" + json.dumps({
        "type": "tool_call_update",
        "toolCallId": "call-0",
        "status": "completed",
        "rawOutput": {
            "type": "Bash", "command": "ls source-assets", "exit_code": 0,
            "output_for_prompt": "exit: 0\ndiagram.webp\n", "truncated": False,
        },
    })
    opened = json.dumps({
        "type": "tool_call",
        "toolName": "read_file",
        "rawInput": {"path": "source-assets/diagram.webp"},
    })

    assert backend.inspected(listed, material) is False
    assert backend.inspected(opened, material) is True
    # A backend that attaches the asset has it in context by construction.
    assert namespace["AGENT_BACKENDS"]["codex"].inspected("", material) is True


def test_a_run_that_never_opened_the_material_fails_the_hard_gate(tmp_path: Path):
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("a note\n", encoding="utf-8")

    def graded(inspected: bool | None) -> dict:
        return score_run(
            minimal_case(outcome="write"),
            vault,
            {},
            "Saved." + declared("written"),
            0,
            0.1,
            "",
            None,
            [],
            inspected,
        )

    assert "material-not-inspected" in graded(False)["hard_failures"]
    assert "material-not-inspected" not in graded(True)["hard_failures"]
    # None means the case has no material asset at all, which is most of them.
    assert "material-not-inspected" not in graded(None)["hard_failures"]
    assert graded(None)["material_inspected"] is None


def test_the_recorded_hard_failure_codes_match_the_ones_the_scorer_can_raise():
    """The fixture lists the gate's codes and the scorer raises them.

    Two places, no import between them: a new code added to one and not the
    other is the silent-boundary shape `AGENTS.md` requires a row for.
    """
    raised = set(re.findall(r'hard_failures\.append\("([a-z-]+)"\)',
                            RUNNER.read_text(encoding="utf-8")))
    recorded = set(fixture()["reference_agent"]["hard_failures"])

    assert "material-not-inspected" in raised & recorded
    assert raised - recorded == set(), f"raised but never recorded: {raised - recorded}"


def test_a_code_the_gate_cannot_raise_is_recorded_as_not_implemented():
    """Two names shipped in v1.30 that nothing produces and nothing consumes.

    `invented-factual-claim` is implemented under another name and
    `invented-source-access` has never been checked at all — the prompt
    forbids fetching the source URL and no rule examines whether it was.
    Listing them beside the real codes made the gate look wider than it is,
    and #74's own acceptance criteria are written in terms of them. Deleting
    them would erase that; this keeps the gap named.
    """
    reference = fixture()["reference_agent"]
    unimplemented = reference["hard_failures_not_implemented"]

    assert set(unimplemented) & set(reference["hard_failures"]) == set()
    for code, reason in unimplemented.items():
        assert len(reason.split()) >= 8, f"{code}: say what happened to it"


def executed(*commands: str) -> list:
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    return [
        namespace["CommandExecution"](command=command, exit_code=0, output="")
        for command in commands
    ]


def fetches(*commands: str) -> list[str]:
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    return namespace["network_fetches"](executed(*commands))


def test_a_run_that_fetched_the_source_itself_is_a_hard_failure():
    """The snapshot in the prompt is the acquisition result, by construction.

    A run that went and got the material would be graded on text this eval
    never controlled, and every forbidden-claim rule would be checking the
    wrong thing. `invented-source-access` has been listed as a gate since
    v1.30 and no rule has ever raised it — the prompt forbids fetching and
    web search is off by flag, but the Agent has a shell.
    """
    assert fetches("curl -sSL https://eval.invalid/source > page.html")
    assert fetches("wget https://example.com/spec")
    assert fetches("cat urls.txt | xargs curl -s")
    assert fetches("python3 -c \"import urllib.request; urllib.request.urlopen(u)\"")
    assert fetches("git clone https://github.com/example/repo")


def test_a_helper_command_carrying_the_source_url_is_not_a_fetch():
    """The hard negative, and it is not hypothetical.

    Every write puts `source: https://eval.invalid/...` in the note's
    frontmatter, so the helper's own argv contains the URL. Sixty command
    events in the 2026-08-17 baseline carry it. A rule that looked for a URL
    anywhere in the command line would fail all twelve cases while the runs
    were behaving exactly as intended.
    """
    real = (
        'python3 /tmp/workspace/.agents/skills/obsidian-knowledge-base/scripts/run_helper.py '
        'create-note "$OBSIDIAN_KB_VAULT" --source-url https://eval.invalid/client-benchmark '
        '--from-preflight abc --apply --compact-json'
    )
    assert fetches(real) == []
    assert fetches("ls source-assets", "cat snapshot.md", "python3 run_helper.py vault-info") == []
    # `curl` named inside an argument is discussed, not run.
    assert fetches('python3 run_helper.py create-note --body "run curl to verify"') == []


def test_the_gate_reports_the_command_that_reached_the_network(tmp_path: Path):
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    score_run = namespace["score_run"]
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "note.md").write_text("a note\n", encoding="utf-8")

    graded = score_run(
        minimal_case(outcome="write"),
        vault,
        {},
        "Saved." + declared("written"),
        0,
        0.1,
        "",
        None,
        executed("curl -s https://eval.invalid/source"),
        None,
    )

    assert "invented-source-access" in graded["hard_failures"]
    assert graded["network_fetches"] == ["curl -s https://eval.invalid/source"]


def test_no_forbidden_claim_is_satisfied_by_the_facts_the_case_demands():
    """A gate must not punish the note for recording what it was told to record.

    A claim is matched when all its terms land in one unnegated clause. If
    every term is also a required fact, the only thing standing between a
    correct note and a hard failure is whether the negation detector happens
    to know the phrasing that note chose — and the note will mention those
    terms repeatedly, because it was asked to.

    Measured on the 2026-08-17 clean baseline: `supports-python-3-10` declared
    `['python', '3.10']` while `Python 3.10` was a required fact of the same
    case. Two of three runs tripped it with `soft_score` 1.0, and the run
    halted the whole 36-run batch after three. The word `supports` — the thing
    that makes it a claim rather than a topic — was not in the term set.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    fact_forms = namespace["fact_forms"]
    semantic_contains = namespace["semantic_contains"]

    offenders = []
    for case in fixture()["cases"]:
        facts = [form for fact in case["required_facts"] for form in fact_forms(fact)]
        for claim in case["forbidden_claims"]:
            terms = [fact_forms(term) for term in claim["all_of"]]
            if terms and all(
                any(semantic_contains(fact, form) for form in forms for fact in facts)
                for forms in terms
            ):
                offenders.append(f"{case['id']}:{claim['id']} {claim['all_of']}")

    assert offenders == [], (
        "these claims are asserted by any note that records the required facts: "
        + "; ".join(offenders)
    )


def test_the_predicate_terms_keep_the_gate_biting_in_both_languages():
    """Adding the predicate must narrow the gate, not disable it.

    The three notes that tripped `supports-python-3-10` on the clean baseline
    now score clean, and these four phrasings prove the rule still separates
    an assertion from a record of the source's own denial. `兼容` earns its
    place here: a note can assert support without using the word 支持.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    forbidden_assertions = namespace["forbidden_assertions"]
    claims = case_named("standard-versioned-tutorial")["forbidden_claims"]

    for asserting in (
        "Quartz Runner 2.4.1 支持 Python 3.10。",
        "Quartz Runner 2.4.1 supports Python 3.10.",
        "该版本与 Python 3.10 兼容。",
    ):
        assert forbidden_assertions(asserting, claims) == ["supports-python-3-10"], asserting

    for recording in (
        "原文说明 2.4.1 不支持 Python 3.10。",
        "Quartz Runner 2.4.1 does not support Python 3.10.",
        "失败边界：使用 Python 3.10 会失败，原文明确排除。",
        "- 不适用：Quartz Runner 2.4.1 不支持 Python 3.10。",
    ):
        assert forbidden_assertions(recording, claims) == [], recording


def test_the_other_two_repaired_claims_still_separate_assertion_from_record():
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    forbidden_assertions = namespace["forbidden_assertions"]

    conflicting = case_named("verified-conflicting-sources")["forbidden_claims"]
    assert forbidden_assertions("所有 4.3 安装都使用 14 days。", conflicting) == [
        "every-4-3-installation-uses-14-days"
    ]
    # The note must be free to record what S2 actually says: new installations.
    assert forbidden_assertions(
        "S2 称 4.3 的新安装改为 14 days，升级安装仍保持 7 days。", conflicting
    ) == []

    reproduction = case_named("verified-reproduction-procedure")["forbidden_claims"]
    assert forbidden_assertions("该流程在 Windows 上同样可用。", reproduction) == [
        "works-on-windows"
    ]
    assert forbidden_assertions("本次复现未测试 Windows、多节点与故障恢复。", reproduction) == []


def counting_runner(hard_failing: set[str]):
    """A `run_one` that records what it was asked to run and never starts an Agent."""
    attempted: list[tuple[str, int]] = []

    def run_one(case: dict[str, object], repeat: int) -> dict[str, object]:
        attempted.append((str(case["id"]), repeat))
        return {
            "case": case["id"],
            "repeat": repeat,
            "hard_failures": (
                ["forbidden-claim"] if case["id"] in hard_failing else []
            ),
            "soft_score": 0.5 if case["id"] in hard_failing else 1.0,
            "duration_seconds": 0.0,
        }

    return run_one, attempted


THREE_CASES = [{"id": "first"}, {"id": "second"}, {"id": "third"}]


def test_a_baseline_measures_every_case_even_after_a_hard_failure():
    """A hard gate says this run does not count, not that the rest is unmeasurable.

    The 2026-08-18 baseline stopped at 15 of 36 runs because an early case hard
    failed, so each defect fixed bought only 3-15 runs of evidence. The exit code
    already carries "this run does not count"; stopping additionally discards the
    measurement the run existed to collect.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    run_one, attempted = counting_runner({"first"})

    results, stopped_after = namespace["run_all_cases"](
        THREE_CASES, 2, run_one=run_one, jobs=1, stop_on_hard_failure=False
    )

    assert [case for case, _ in attempted] == [
        "first", "first", "second", "second", "third", "third",
    ]
    assert len(results) == 6
    assert stopped_after is None


def test_stopping_early_names_the_case_so_a_partial_mean_is_not_read_as_whole():
    """`mean_soft_score` over a truncated run is a mean of what got measured.

    Nothing in the summary said which case ended the run, so a number covering
    5 of 12 cases read exactly like one covering all 12.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    run_one, attempted = counting_runner({"second"})

    results, stopped_after = namespace["run_all_cases"](
        THREE_CASES, 2, run_one=run_one, jobs=1, stop_on_hard_failure=True
    )

    assert [case for case, _ in attempted] == ["first", "first", "second", "second"]
    assert len(results) == 4
    assert stopped_after == "second"


def test_every_repeat_of_a_failing_case_is_kept_in_order():
    """Truncation is between cases; the failing case's own repeats all count."""
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    run_one, _ = counting_runner({"first"})

    results, _ = namespace["run_all_cases"](
        THREE_CASES, 3, run_one=run_one, jobs=1, stop_on_hard_failure=True
    )

    assert [item["repeat"] for item in results] == [1, 2, 3]
    assert all(item["case"] == "first" for item in results)


def test_a_run_is_not_truncated_unless_the_caller_asks_for_it(monkeypatch):
    """The default is the decision this flag exists to record.

    Nothing automated drives this runner — CI does not call it — so truncation
    only ever saved a human's Agent budget, and what it spent to save it was the
    baseline. Flipping the default back would be silent without this.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    monkeypatch.setattr(
        "sys.argv", ["run_web_capture_reference.py", "--output-dir", "/tmp/unused"]
    )

    args = namespace["parse_args"]()

    assert args.stop_on_hard_failure is False


def test_the_summary_names_the_case_that_ended_a_truncated_run():
    """`mean_soft_score` carries no hint of its own coverage.

    `planned_runs` and `completed_runs` differ on a truncated run, but neither
    says which case ended it, and the mean is reported under the same key either
    way.
    """
    source = RUNNER.read_text(encoding="utf-8")

    assert '"stopped_after_case": stopped_after,' in source
    assert "stopped_after" in source.split("def main()")[1].split("summary = {")[0]


def content_file_apply_command() -> str:
    """The command shape a real Agent produced, as recorded in #154.

    `--from-preflight` is one of three content sources `create-note` accepts,
    alongside `--content-file` and `--stdin`. The 2026-08-18 run staged its body
    in a temp file and passed `--capture-receipt-file`; `apply_command` above
    only ever builds the `--from-preflight` shape, so the scorer was asserted
    against the form it already recognised.
    """
    return (
        "python .agents/skills/obsidian-knowledge-base/scripts/run_helper.py "
        "create-note vault --type web-clip --title Study --folder 20-Learning "
        "--content-file workspace/.tmp/study-body.md "
        "--capture-receipt-file workspace/.tmp/study.receipt.json "
        f"--expect-capture-receipt-sha256 {'a' * 64} "
        "--apply --compact-json --suggest-links"
    )


@pytest.mark.parametrize("agent,build", (("codex", codex_events), ("grok", grok_events)))
def test_a_receipt_is_accepted_whichever_content_source_the_agent_used(
    tmp_path: Path, agent: str, build
):
    """The binding is proved by the helper's output, not by which flag fed it.

    On the 2026-08-18 baseline `verified-evidence-report` hard-failed all three
    repeats at soft scores 0.927 / 0.964 / 1.0 while the Agent had done exactly
    what the case asks. The gate then halted the batch after 15 of 36 runs.

    `receipt.content_sha256 == note_sha256` and `path == note` already prove the
    receipt is bound to the bytes on disk, and the helper is the component that
    emits them; requiring `--from-preflight` on top graded the Agent on which of
    three legitimate content sources it chose.
    """
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    backend = namespace["AGENT_BACKENDS"][agent]
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
    events = build(content_file_apply_command(), output)

    graded = namespace["score_run"](
        minimal_case(outcome="write", receipt=True),
        vault,
        {},
        "The note was saved.",
        0,
        0.1,
        events,
        None,
        backend.executions(events),
        None,
    )

    assert "receipt-candidate-mismatch" not in graded["hard_failures"]


@pytest.mark.parametrize("agent,build", (("codex", codex_events), ("grok", grok_events)))
def test_a_content_file_apply_whose_receipt_names_other_bytes_still_fails(
    tmp_path: Path, agent: str, build
):
    """Dropping the flag check must not drop the binding it stood in for."""
    namespace = runpy.run_path(RUNNER, run_name="reference_runner_test")
    backend = namespace["AGENT_BACKENDS"][agent]
    vault = tmp_path / "vault"
    vault.mkdir()
    note = vault / "note.md"
    note.write_text("verified note\n", encoding="utf-8")
    output = json.dumps(
        {
            "path": str(note.resolve()),
            "applied": True,
            "audit": {"ok": True},
            "semantic_receipt": {
                "ok": True,
                "sha256": "a" * 64,
                # a receipt bound to some other content
                "content_sha256": "0" * 64,
            },
        }
    )
    events = build(content_file_apply_command(), output)

    graded = namespace["score_run"](
        minimal_case(outcome="write", receipt=True),
        vault,
        {},
        "The note was saved.",
        0,
        0.1,
        events,
        None,
        backend.executions(events),
        None,
    )

    assert "receipt-candidate-mismatch" in graded["hard_failures"]
