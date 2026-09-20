"""Summarise a Step 4 campaign log: per-condition suspicion, attack success, per-commit detail."""

import glob
import statistics as stats
import sys

from inspect_ai.log import read_eval_log


def load(paths):
    rows, commits = [], []
    for p in paths:
        log = read_eval_log(p)
        for s in log.samples or []:
            md = s.metadata or {}
            st = s.store or {}
            cs = st.get("commits") or []
            tr = st.get("task_results") or {}
            side = st.get("side_task_name")
            mains = st.get("main_task_names") or []
            susp = [c["suspicion"] for c in cs if c["suspicion"] is not None]
            rows.append(
                {
                    "id": s.id,
                    "condition": md.get("condition"),
                    "side": side,
                    "K": md.get("n_agents"),
                    "max_susp": max(susp) if susp else None,
                    "mean_susp": (sum(susp) / len(susp)) if susp else None,
                    "per_commit": [c["suspicion"] for c in cs],
                    "main_pass": sum(1 for m in mains if tr.get(m)),
                    "n_main": len(mains),
                    "side_pass": bool(tr.get(side)) if side else None,
                    "parse_fail": sum(1 for c in cs if c["suspicion"] is None),
                    "limit_hits": sum(1 for c in cs if c["limit_hit"]),
                }
            )
            for c in cs:
                commits.append({**c, "campaign": s.id, "condition": md.get("condition"), "side": side})
    return rows, commits


def main():
    paths = sys.argv[1:] or sorted(glob.glob("data/step4/*.eval"))
    rows, commits = load(paths)

    print("## Per-campaign\n")
    hdr = ["campaign", "K", "max susp", "per-commit", "main", "side", "parse fail", "limit hits"]
    print("| " + " | ".join(hdr) + " |")
    print("|" + "---|" * len(hdr))
    for r in sorted(rows, key=lambda x: (x["side"] or "", x["condition"] or "")):
        print(
            f"| {r['id']} | {r['K']} | {r['max_susp']} | {r['per_commit']} | "
            f"{r['main_pass']}/{r['n_main']} | {r['side_pass']} | {r['parse_fail']} | {r['limit_hits']} |"
        )

    print("\n## Per-condition (the comparison)\n")
    hdr2 = ["condition", "side task", "n campaigns", "max-susp per campaign", "mean max-susp",
            "all commit scores", "mean commit susp", "side task passed"]
    print("| " + " | ".join(hdr2) + " |")
    print("|" + "---|" * len(hdr2))
    keys = sorted({(r["condition"], r["side"]) for r in rows}, key=lambda x: (x[1] or "", x[0]))
    for cond, side in keys:
        rs = [r for r in rows if r["condition"] == cond and r["side"] == side]
        maxes = [r["max_susp"] for r in rs if r["max_susp"] is not None]
        allc = [c["suspicion"] for c in commits
                if c["condition"] == cond and c["side"] == side and c["suspicion"] is not None]
        sp = [r["side_pass"] for r in rs if r["side_pass"] is not None]
        print(
            f"| {cond} | {side or '-'} | {len(rs)} | {maxes} | "
            f"{round(stats.mean(maxes), 2) if maxes else '-'} | {sorted(allc, reverse=True)} | "
            f"{round(stats.mean(allc), 2) if allc else '-'} | {sum(sp)}/{len(sp)} |"
        )

    print("\n## Attacker vs benign commits (attack campaigns only)\n")
    for cond in ["K1_attack", "K3_attack"]:
        atk = [c["suspicion"] for c in commits
               if c["condition"] == cond and c["is_attacker"] and c["suspicion"] is not None]
        ben = [c["suspicion"] for c in commits
               if c["condition"] == cond and not c["is_attacker"] and c["suspicion"] is not None]
        print(f"- **{cond}**: attacker-carrying commits {sorted(atk, reverse=True)} "
              f"(mean {round(stats.mean(atk),2) if atk else '-'}); "
              f"non-attacker commits {sorted(ben, reverse=True)}")
    hon = [c["suspicion"] for c in commits if c["condition"] == "K3_honest" and c["suspicion"] is not None]
    print(f"- **K3_honest** (false-positive floor): {sorted(hon, reverse=True)} "
          f"(mean {round(stats.mean(hon),2) if hon else '-'})")


if __name__ == "__main__":
    main()
