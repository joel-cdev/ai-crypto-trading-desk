"""
Debate core
===========
Each pipeline agent convenes a 4-member panel of sub-agents. Every sub-agent
casts a stance + a 0-100 confidence that is COMPUTED in plain Python from real
signals. `tally_votes` turns the panel into a verdict; the verdict flows down
the pipeline.

The natural-language *arguments* are optional flavour: `narrate_all` makes a
SINGLE batched OpenAI call to write one line per sub-agent across every panel
(fast, ~1 call). With no key it is a no-op and the templated rationales each
agent set inline are used — so the debate is fully deterministic and offline.

The LLM only phrases pre-computed stances; it never changes a vote or a number.
"""

from lib.llm import chat_json


def member(name: str, stance: str, confidence: int, rationale: str) -> dict:
    return {"name": name, "stance": stance,
            "confidence": int(max(0, min(100, confidence))), "rationale": rationale}


def make_panel(title: str, members: list, neutral: str = "HOLD") -> dict:
    """Tally a panel of sub-agents into a verdict + verdict confidence."""
    tally = {}
    for m in members:
        tally[m["stance"]] = tally.get(m["stance"], 0) + 1

    top = max(tally.values())
    winners = [s for s, n in tally.items() if n == top]
    if len(winners) == 1:
        verdict = winners[0]
    elif neutral in winners:
        verdict = neutral            # tie -> prefer the neutral stance
    else:
        # tie between non-neutral stances -> side with the higher mean confidence
        verdict = max(winners, key=lambda s: _mean_conf(members, s))

    verdict_confidence = round(_mean_conf(members, verdict))
    return {
        "title": title,
        "members": members,
        "tally": tally,
        "verdict": verdict,
        "verdict_confidence": verdict_confidence,
    }


def _mean_conf(members, stance):
    vals = [m["confidence"] for m in members if m["stance"] == stance]
    return sum(vals) / len(vals) if vals else 0


def narrate_all(panels: dict, context: str):
    """One small batched OpenAI call to add a one-line `debate_summary` to each
    panel (how the room argued it out). The per-member rationales — which cite
    the real indicator values — are left untouched. Mutates panels in place;
    no-op without a key, so the demo stays fast and fully offline-capable."""
    spec = {}
    for key, panel in panels.items():
        spec[key] = {
            "verdict": panel["verdict"],
            "votes": [f"{m['name']}:{m['stance']}" for m in panel["members"]],
        }

    system = (
        "You script a trading war-room. For EACH panel, write ONE punchy sentence (max 22 words) "
        "summarising how the members debated to their verdict. Use ONLY the given stances; do not "
        "invent or change any number or stance. Return JSON mapping each panel key to a string."
    )
    user = f"Context: {context}\n\nPanels:\n{spec}"
    data = chat_json(system, user, max_tokens=300)
    if not data:
        return
    for key, panel in panels.items():
        summary = data.get(key)
        if isinstance(summary, str) and summary.strip():
            panel["debate_summary"] = summary.strip()
