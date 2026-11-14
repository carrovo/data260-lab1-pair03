from loadtest.summarize import stats


def result_row(elapsed, *, timestamp=0, success="true"):
    return {
        "elapsed": str(elapsed),
        "timeStamp": str(timestamp),
        "success": success,
    }


def test_percentiles_use_the_standard_nearest_rank_method():
    summary = stats(
        [result_row(elapsed, timestamp=elapsed * 1000) for elapsed in range(1, 101)]
    )

    assert summary["p50"] == 50
    assert summary["p95"] == 95
    assert summary["p99"] == 99


def test_stats_handles_empty_and_single_value_inputs():
    assert stats([]) is None

    summary = stats([result_row(42)])

    assert summary["n"] == 1
    assert summary["p50"] == 42
    assert summary["p95"] == 42
    assert summary["p99"] == 42
    assert summary["errors"] == 0
    assert summary["err"] == 0
