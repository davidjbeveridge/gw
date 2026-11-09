"""Summarize the allowlisted public evidence without running models or tools."""

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean


def summarize(data):
    continuity = data["continuity"]
    scores = defaultdict(list)
    for row in continuity["ratings"]:
        scores[row["task_id"], row["arm"]].append(row["score"])
    tasks = sorted({task for task, _ in scores})
    quality = mean(mean(scores[t, "B"]) - mean(scores[t, "A"]) for t in tasks)
    assert quality == continuity["quality_difference"]

    configured = data["configured_nonsemantic"]
    maintenance = {}
    for arm in ("A", "B"):
        rows = [r for r in configured["attempts"] if r["arm"] == arm]
        accepted = sum(r["captured"] and r["accepted_artifact"] is True for r in rows)
        missing = sum(not r["captured"] for r in rows)
        maintenance[arm] = {
            "assigned": len(rows),
            "known_accepted": accepted,
            "unknown": missing,
            "acceptance_bounds": [accepted / len(rows), (accepted + missing) / len(rows)],
            "tokens": sum(r["tokens"] for r in rows),
        }

    context = data["context_repair"]
    pairs = context["pairs"]
    accepted = {arm: sum(p[arm]["accepted"] for p in pairs) for arm in ("A", "C")}
    tokens = {arm: sum(p[arm]["tokens"] for p in pairs) for arm in ("A", "C")}
    gains = sum(p["C"]["accepted"] and not p["A"]["accepted"] for p in pairs)
    losses = sum(p["A"]["accepted"] and not p["C"]["accepted"] for p in pairs)
    jointly = accepted["C"] - gains
    saving = 1 - tokens["C"] / tokens["A"]
    adequate_answers = accepted["C"] >= 10 and losses == 0
    assert gains - losses == context["gates"]["net_gains"]
    assert jointly == context["gates"]["jointly_accepted"]
    assert abs(saving - context["gates"]["aggregate_token_saving"]) < 1e-12
    return {
        "continuity": {"episodes": len(continuity["ratings"]), "tasks": len(tasks),
                       "equal_task_mean_quality_difference": quality,
                       "resources": continuity["resources"]},
        "configured_nonsemantic": maintenance,
        "context_repair": {"pairs": len(pairs), "accepted": accepted, "tokens": tokens,
                           "gains": gains, "losses": losses, "jointly_accepted": jointly,
                           "token_change_percent": -100 * saving,
                           "quality_branch": adequate_answers and gains - losses >= 2,
                           "token_saving_branch": adequate_answers and jointly >= 8 and saving >= 0.15},
    }


if __name__ == "__main__":
    path = Path(__file__).with_name("results.json")
    print(json.dumps(summarize(json.loads(path.read_text(encoding="utf-8"))), indent=2))
