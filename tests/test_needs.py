from state_of_soroban.stages.needs import coverage, percentile, tokenise


def test_percentile_spreads_values_and_orders_them():
    ranks = percentile({"a": 1.0, "b": 5.0, "c": 9.0, "d": 9.0})

    assert ranks["a"] < ranks["b"] < ranks["c"]
    assert ranks["c"] == ranks["d"]
    assert all(0 <= value <= 1.2 for value in ranks.values())


def test_coverage_counts_full_tools_more_than_partial_ones():
    assert coverage([]) == 0
    assert coverage([{"relation": "partial"}]) < coverage([{"relation": "covers"}])
    assert coverage([{"relation": "covers"}, {"relation": "covers"}]) == 1.0


def test_titles_are_tokenised_without_filler_words():
    assert tokenise("Add support for the Soroban fuzzing") == [
        "support",
        "soroban",
        "fuzzing",
    ]
