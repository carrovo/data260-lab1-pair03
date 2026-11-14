"""Turn JMeter result files into the tables and the graph the report needs.

  python loadtest/summarize.py crud <label>        # reads loadtest/k8s_<label>_<users>.jtl
  python loadtest/summarize.py assistant <label>   # reads loadtest/assistant_<label>_<users>.jtl

crud: average response time, throughput (requests/s) and error rate for login, job search,
application submission and event search/registration at each concurrency level, plus
average-response-time-vs-concurrency graph (avg_response_<label>.png).
assistant: p50, p95, p99 latency, average, throughput and error rate per level.
Writes the Markdown to loadtest/summary_<mode>_<label>.md and prints it.
"""
import csv, glob, re, statistics, sys
from pathlib import Path

HERE = Path(__file__).parent
GROUPS = {
    "Login": ["Student login"],
    "Job search": ["Search jobs by keyword", "Search jobs by city"],
    "Application submission": ["Apply with resume"],
    "Event search / registration": ["Search events", "Register for event"],
}


def read(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def stats(rows):
    if not rows:
        return None
    el = sorted(int(r["elapsed"]) for r in rows)
    start = min(int(r["timeStamp"]) for r in rows)
    end = max(int(r["timeStamp"]) + int(r["elapsed"]) for r in rows)
    span = max((end - start) / 1000, 0.001)
    err = sum(1 for r in rows if r["success"] != "true")

    def pct(p):
        return el[min(len(el) - 1, int(round(p / 100 * len(el) + 0.5)) - 1)]

    return {"n": len(rows), "avg": statistics.mean(el), "tput": len(rows) / span,
            "err": 100 * err / len(rows), "p50": pct(50), "p95": pct(95), "p99": pct(99)}


def levels(prefix):
    found = {}
    for p in glob.glob(str(HERE / f"{prefix}_*.jtl")):
        m = re.search(r"_(\d+)\.jtl$", p)
        if m:
            found[int(m.group(1))] = p
    return dict(sorted(found.items()))


def main(mode, label):
    out = []
    if mode == "crud":
        files = levels(f"k8s_{label}")
        data = {lvl: read(p) for lvl, p in files.items()}
        series = {}
        for g, names in GROUPS.items():
            out += [f"### {g}", "", "| Users | Requests | Avg (ms) | Throughput (req/s) | Error rate |", "|---:|---:|---:|---:|---:|"]
            for lvl, rows in data.items():
                s = stats([r for r in rows if r["label"] in names])
                if s:
                    out.append(f"| {lvl} | {s['n']} | {s['avg']:.0f} | {s['tput']:.1f} | {s['err']:.2f}% |")
                    series.setdefault(g, []).append((lvl, s["avg"]))
            out.append("")
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            plt.figure(figsize=(8, 4.5))
            for g, pts in series.items():
                plt.plot([p[0] for p in pts], [p[1] for p in pts], marker="o", label=g)
            plt.yscale("log"); plt.xticks(sorted({p[0] for pts in series.values() for p in pts}))
            plt.xlabel("Concurrent users (total, all scenarios)")
            plt.ylabel("Average response time (ms, log scale)")
            plt.title(f"Pair 03: average response time vs concurrency ({label})")
            plt.grid(alpha=0.3); plt.legend(); plt.tight_layout()
            plt.savefig(HERE / f"avg_response_{label}.png", dpi=150)
            out.append(f"Graph: loadtest/avg_response_{label}.png")
        except ImportError:
            out.append("(matplotlib not installed: no graph written)")
    else:
        files = levels(f"assistant_{label}")
        out += ["| Concurrent users | Requests | p50 (ms) | p95 (ms) | p99 (ms) | Avg (ms) | Throughput (req/s) | Error rate |", "|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for lvl, p in files.items():
            s = stats([r for r in read(p) if r["label"] == "Assistant chat"])
            if s:
                out.append(f"| {lvl} | {s['n']} | {s['p50']} | {s['p95']} | {s['p99']} | {s['avg']:.0f} | {s['tput']:.2f} | {s['err']:.2f}% |")
    text = "\n".join(out)
    (HERE / f"summary_{mode}_{label}.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
