"""Generate the corpus the v1.30 directional labels always implied (#75).

Written from the labels alone, before any scorer exists. Each source note gets
one sentence that names its positive target and says what it uses it for —
taken from that case's own `evidence` field — and shares a topic word with its
hard negative while never naming it.

Note shapes follow what the reference Vault actually contains, measured today:
frontmatter with `type`/`date`/`tags`, an H1, and `##` sections.
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
LABELS = json.loads(
    (ROOT / "tests" / "fixtures" / "directed_link_eval_cases.json").read_text(
        encoding="utf-8"
    )
)

# One dependency sentence per positive case, phrased with that case's own verb.
# `{t}` is replaced by a wikilink to the target.
DEPENDS = {
    "pos-01": "The ceiling cites the saturation point measured in {t}.",
    "pos-02": "This decision names {t} as the privacy constraint it answers to.",
    "pos-03": "Candidate identity is delegated to {t}.",
    "pos-04": "Every expansion term is traced to {t}.",
    "pos-05": "This rule was adopted in response to {t}.",
    "pos-06": "The budget is expressed as a multiple of the P95 in {t}.",
    "pos-07": "The design references the scalar and list examples in {t}.",
    "pos-08": "The workflow links to {t} for its verification stage.",
    "pos-09": "The gate's corpus is selected from the cases in {t}.",
    "pos-10": "This policy cites the incompatible custom headings found by {t}.",
    "pos-11": "Reconstructability is verified by {t}, which consumes an archive in this format.",
    "pos-12": "Equal scores are resolved by importing the path-order rule from {t}.",
    "pos-13": "The capture flow branches on the availability states in {t}.",
    "pos-14": "Immutability is proven with the before-and-after hashes from {t}.",
    "pos-15": "Candidate priority follows the failure categories in {t}.",
    "pos-16": "The gate fails when any run in {t} has a hard failure.",
}

# What each source note is about, in its own words. The shared word with the
# hard negative appears here — that is the collision the negatives exist for.
ABOUT = {
    "Retry Policy": "How this service retries a failed call, and where the delay stops growing.",
    "Offline Search Decision": "Why search runs locally rather than against a hosted index.",
    "Capture Receipt Contract": "What a capture receipt must bind so a note can be checked later.",
    "Bilingual Query Expansion": "How a query written in one language reaches notes written in the other.",
    "Zero-write Failure Rule": "What happens when a capture cannot complete: nothing is written.",
    "Search Latency Budget": "How slow a search is allowed to be before it counts as a regression.",
    "Alias Matching Design": "How an alias in frontmatter resolves to the note that declares it.",
    "Verified Capture Workflow": "The stricter capture path, and what makes a capture verified.",
    "No-answer Gate": "When retrieval should return nothing rather than the closest of several answers.",
    "Template Compatibility Policy": "How this project treats a Vault whose templates differ from its own.",
    "Source Archive Format": "The byte-level format an archived source is written in.",
    "Deterministic Ranking": "Why two runs over an unchanged Vault return the same order.",
    "Material Image Capture": "When an image is material to a capture, and what to do when it is missing.",
    "Read-only Retrieval": "The guarantee that retrieval never changes a file.",
    "Semantic Candidate Order": "The order candidates are considered in, and why it is not alphabetical.",
    "Release Quality Gate": "What has to hold before a release goes out.",
}

# Hard-negative bodies: the same word, a different world. None of them names or
# links to its source, and none is the kind of note a source would cite.
NEGATIVE_ABOUT = {
    "HTTP Client Library Survey": "A comparison of client libraries. Each section lists timeouts, connection pooling and whether the library retries by default.",
    "Search Icon Design": "Notes on the magnifying-glass icon: stroke weight, optical size, and how the search affordance reads at 16px.",
    "Receipt Printer Review": "A thermal receipt printer tested for a small shop. Paper cost, cutter reliability, and how legible the receipt is after a week in a wallet.",
    "Language Learning Schedule": "A weekly plan for studying two languages: which mornings go to which, and how review is spaced.",
    "Empty File Cleanup": "A housekeeping routine that removes zero-byte files left behind by interrupted downloads.",
    "Quarterly Budget Notes": "Where the quarter's budget went. Headcount, tooling, and the line items that came in over.",
    "Shell Alias Collection": "Aliases collected over the years. Short names for long commands, and the two that turned out to be dangerous.",
    "Camera Capture Settings": "Settings for capture on the camera: shutter, ISO, and the bracketing preset used indoors.",
    "Interview Answers": "Answers prepared for interview questions, with the ones that landed badly marked.",
    "Presentation Templates": "Slide templates: title layouts, the chart palette, and which template to use for an external deck.",
    "Museum Archive Visit": "A visit to the museum archive. What the reading room allows, how requests are queued, and what could be photographed.",
    "University Rankings": "How universities are ranked, which inputs dominate, and why the order moves so little year to year.",
    "Image Compression Tips": "Getting an image smaller without visible loss: format choice, quality settings, and when to stop.",
    "Reading List": "Books to read, with the ones already read struck through and a line on each.",
    "Election Candidates": "The candidates standing this cycle and where each of them differs from the others.",
    "Airport Departure Gates": "How departure gates are assigned, why they change late, and how far the walk is from security.",
}

# Positive-target bodies: the note that does the explaining. It does *not* link
# back — the relation is directional, and a symmetric corpus could not show that.
POSITIVE_ABOUT = {
    "Backoff Measurements": "Measured latency under load. Saturation appears at 800 ms; past that, added delay buys nothing.",
    "Index Privacy Threat Model": "What an attacker learns from a hosted index: query contents, timing, and the shape of the corpus.",
    "Candidate Hash Algorithm": "The hash used to identify a candidate: input normalisation, algorithm, and what a collision would mean.",
    "Vault Terminology Table": "The bounded table of term pairs this Vault uses across its two languages.",
    "Unavailable Source Incident": "The incident: a source went unavailable mid-capture and a half-written note was left behind.",
    "Vault Scan Benchmark": "Scan timings over a 200-note Vault. P50 and P95, measured cold and warm.",
    "Frontmatter Alias Examples": "Alias frontmatter as it appears in the wild: a bare scalar, a list, and the empty forms.",
    "Independent Audit Procedure": "The second pass: who runs it, what they re-check, and what they are not allowed to see first.",
    "False-positive Casebook": "Cases where a confident answer was wrong, grouped by what produced the confidence.",
    "Customized Vault Survey": "A survey of Vaults with custom templates. Which headings differ, and how far.",
    "Archive Replay Test": "Replaying an archive to confirm the original can still be reconstructed byte for byte.",
    "Tie-break Specification": "How equal scores are ordered: by path, case-folded first, then raw.",
    "Image Availability Matrix": "Every availability state an image can be in, and what each one permits.",
    "Filesystem Snapshot Method": "Hashing every file before and after an operation to prove nothing changed.",
    "Lexical Baseline Report": "Where lexical ranking misses, grouped into failure categories with counts.",
    "Reference Agent Runs": "Repeated runs against the reference Vault, each recorded with its outcome.",
}

FOLDERS = {
    "source": "20-Learning/design",
    "positive": "20-Learning/evidence",
    "negative": "20-Learning/unrelated",
}


def slug(title: str) -> str:
    # The filename *is* the title, which is how Obsidian resolves [[Title]] and
    # how the reference Vault actually names its notes. Slugifying broke every
    # link in the first draft: the body said [[Backoff Measurements]] and the
    # file was Backoff-Measurements.md, so nothing resolved.
    return title.replace("/", "-")


def main() -> None:
    positives = {case["source"]: case for case in LABELS["positive"]}
    negatives = {case["source"]: case for case in LABELS["hard_negative"]}
    notes: list[dict] = []

    for title, about in POSITIVE_ABOUT.items():
        notes.append({
            "path": f"{FOLDERS['positive']}/{slug(title)}.md",
            "title": title,
            "role": "positive-target",
            "body": f"## What this records\n\n{about}\n",
        })
    for title, about in NEGATIVE_ABOUT.items():
        notes.append({
            "path": f"{FOLDERS['negative']}/{slug(title)}.md",
            "title": title,
            "role": "negative-target",
            "body": f"## What this records\n\n{about}\n",
        })

    for title, about in ABOUT.items():
        case = positives[title]
        target = case["target"]
        sentence = DEPENDS[case["id"]].format(t=f"[[{target}]]")
        notes.append({
            "path": f"{FOLDERS['source']}/{slug(title)}.md",
            "title": title,
            "role": "source",
            "body": (
                f"## What this decides\n\n{about}\n\n"
                f"## Why\n\n{sentence}\n"
            ),
        })

    document = {
        "schema_version": 1,
        "purpose": (
            "Notes realising the v1.30 directional labels in "
            "directed_link_eval_cases.json. Written from those labels before any "
            "scorer existed; every dependency sentence restates that case's own "
            "`evidence` field. Synthetic: no real Vault content."
        ),
        "notes": sorted(notes, key=lambda note: note["path"]),
    }
    out = ROOT / "tests" / "fixtures" / "directed_link_corpus.json"
    out.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {out.name}: {len(notes)} notes")
    print(f"  sources {sum(1 for n in notes if n['role'] == 'source')}")
    print(f"  positive targets {sum(1 for n in notes if n['role'] == 'positive-target')}")
    print(f"  negative targets {sum(1 for n in notes if n['role'] == 'negative-target')}")


if __name__ == "__main__":
    main()
