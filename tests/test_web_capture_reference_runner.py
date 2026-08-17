"""Static safety checks for the opt-in reference-Agent runner."""
from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path

import pytest


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
        rendered = " ".join(command) + " " + json.dumps(environment)

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
            assert str(workspace / ".home") in " ".join(command), name
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
        case, vault, {}, "The failover order is unavailable." + stop, 0, 0.1, "", None, []
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
