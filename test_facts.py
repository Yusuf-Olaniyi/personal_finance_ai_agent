from facts import compute_facts


def test_basic_facts():
    f = compute_facts(500000, {"Rent": 200000, "Food": 100000}, [], 0)
    assert f["total_expenses"] == 300000
    assert f["surplus"] == 200000
    assert f["categories"][0]["category"] == "Rent"
    assert f["categories"][0]["percentage"] == 66.7
    assert f["emergency_fund_target"] == 1800000
    assert f["surplus_after_debt"] == 200000


def test_deficit_is_negative():
    f = compute_facts(100000, {"Rent": 150000}, [], 0)
    assert f["surplus"] == -50000