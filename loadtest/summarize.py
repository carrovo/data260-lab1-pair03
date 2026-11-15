"""Turn JMeter result files into the tables and the graph the report needs.

  python loadtest/summarize.py crud <label>        # reads loadtest/k8s_<label>_<users>.jtl
  python loadtest/summarize.py assistant <label>   # reads loadtest/assistant_<label>_<users>.jtl

crud: average response time, throughput (requests/s) and error rate for login, job search,
application submission and event search/registration at each concurrency level, plus
average-response-time-vs-concurrency graph (avg_response_<label>.png).
assistant: p50, p95, p99 latency, average, throughput and error rate per level.
Writes the Markdown to loadtest/summary_<mode>_<label>.md and prints it.
"""
import argparse, csv, glob, math, re, shlex, statistics
from collections import Counter
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
    err = sum(1 for r in rows if r["success"].lower() != "true")

    def pct(p):
        index = math.ceil(p / 100 * len(el)) - 1
        return el[index]

    return {"n": len(rows), "avg": statistics.mean(el), "tput": len(rows) / span,
            "successes": len(rows) - err, "success_rate": 100 * (len(rows) - err) / len(rows),
            "errors": err, "err": 100 * err / len(rows),
            "p50": pct(50), "p95": pct(95), "p99": pct(99)}


def levels(prefix):
    found = {}
    for p in glob.glob(str(HERE / f"{prefix}_*.jtl")):
        m = re.search(r"_(\d+)\.jtl$", p)
        if m:
            found[int(m.group(1))] = p
    return dict(sorted(found.items()))


def assistant_interpretation(results):
    out = []
    for (previous_level, previous), (level, current) in zip(results, results[1:]):
        linear_tput = previous["tput"] * level / previous_level
        if current["p50"] > previous["p50"] and current["tput"] < 0.75 * linear_tput:
            out.append(
                f"Saturation begins at {level} users: p50 rises from "
                f"{previous['p50']} ms to {current['p50']} ms while throughput "
                f"increases only from {previous['tput']:.2f} to {current['tput']:.2f} req/s, "
                "well below linear scaling."
            )
            break

    if results:
        level, result = results[-1]
        if result["errors"]:
            out.append(
                f"The {level}-user level is not reliable in this environment: "
                f"{result['errors']} of {result['n']} Assistant requests failed "
                f"({result['err']:.2f}% error rate)."
            )
        else:
            out.append(f"All {result['n']} requests at {level} users succeeded.")
    return out


def assistant_error_groups(rows):
    return Counter(
        (row["responseCode"], row["responseMessage"])
        for row in rows
        if row["success"].lower() != "true"
    )


def main(mode, label, *, test_environment=None, ollama_version=None, model=None):
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
        command = ["python3", "loadtest/summarize.py", "assistant", label]
        if test_environment:
            command += ["--test-environment", test_environment]
        if ollama_version:
            command += ["--ollama-version", ollama_version]
        if model:
            command += ["--model", model]
        out += [
            f"# Assistant load-test summary ({label})",
            "",
            "Generated from `loadtest/assistant_"
            f"{label}_<users>.jtl` with:",
            "",
            f"`{' '.join(shlex.quote(part) for part in command)}`",
            "",
            "The runner uses 5, 10, 20 and 50 users, a 5-second ramp-up, "
            "3 loops and 500 ms think time. Percentiles use the standard "
            "nearest-rank method and include every `Assistant chat` sample, "
            "including unsuccessful samples.",
            "",
        ]
        if test_environment or ollama_version or model:
            out += ["## Test environment", ""]
            if test_environment:
                out.append(f"- System: {test_environment}")
            if ollama_version:
                out.append(f"- Ollama: {ollama_version}")
            if model:
                out.append(f"- Model: `{model}`")
            out.append("")
        out += [
            "| Concurrent users | Assistant samples | Successes | Errors | Success rate | "
            "p50 (ms) | p95 (ms) | p99 (ms) | Throughput (req/s) |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        results = []
        error_groups = []
        for lvl, p in files.items():
            chats = [r for r in read(p) if r["label"] == "Assistant chat"]
            s = stats(chats)
            if s:
                results.append((lvl, s))
                error_groups.extend(
                    (lvl, count, code, message)
                    for (code, message), count in assistant_error_groups(chats).items()
                )
                out.append(
                    f"| {lvl} | {s['n']} | {s['successes']} | {s['errors']} | "
                    f"{s['success_rate']:.2f}% | {s['p50']} | {s['p95']} | "
                    f"{s['p99']} | {s['tput']:.2f} |"
                )
        if error_groups:
            out += [
                "",
                "## Observed errors",
                "",
                "| Concurrent users | Count | Response code | Response message |",
                "|---:|---:|---|---|",
            ]
            out.extend(
                f"| {level} | {count} | {code} | {message} |"
                for level, count, code, message in error_groups
            )
        interpretation = assistant_interpretation(results)
        if interpretation:
            out += ["", "## Interpretation", ""]
            out.extend(interpretation)
    text = "\n".join(out)
    (HERE / f"summary_{mode}_{label}.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("crud", "assistant"))
    parser.add_argument("label")
    parser.add_argument("--test-environment")
    parser.add_argument("--ollama-version")
    parser.add_argument("--model")
    args = parser.parse_args()
    main(
        args.mode,
        args.label,
        test_environment=args.test_environment,
        ollama_version=args.ollama_version,
        model=args.model,
    )
