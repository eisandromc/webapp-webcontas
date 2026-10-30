from app.domain.calc import DiscountInput, ShareInput, allocate_cents, allocate_equally, equal_percentages, summarize_month
from app.services.periods import default_period_range


def test_equal_percentages_supports_any_number_of_people():
    result = equal_percentages([1, 2, 3])
    assert result == [3334, 3333, 3333]
    assert sum(result) == 10_000


def test_last_person_receives_rounding_residual():
    result = allocate_cents(10_001, [ShareInput(1, 5000, 0), ShareInput(2, 5000, 1)])
    assert result == {1: 5001, 2: 5000}
    assert sum(result.values()) == 10_001


def test_vales_add_discounts_subtract_and_payments_reduce_balance():
    summary = summarize_month(
        [100_00, 50_00],
        [20_00],
        [10_00],
        [ShareInput(1, 6000, 0), ShareInput(2, 4000, 1)],
        {1: 30_00},
        {1: 5_00, 2: -5_00},
    )
    assert summary["expenses_cents"] == 140_00
    assert summary["net_cents"] == 160_00
    assert summary["people"][1]["part_cents"] == 96_00
    assert summary["people"][1]["balance_cents"] == 66_00
    assert summary["people"][1]["accumulated_cents"] == 71_00
    assert summary["people"][2]["part_cents"] == 64_00


def test_negative_entry_reduces_total():
    summary = summarize_month(
        [100_00, -20_00], [], [],
        [ShareInput(1, 5000, 0), ShareInput(2, 5000, 1)], {},
    )
    assert summary["expenses_cents"] == 80_00
    assert summary["people"][1]["part_cents"] == 40_00


def test_equal_discount_is_independent_from_monthly_percentages():
    summary = summarize_month(
        [100_00], [], [],
        [ShareInput(1, 7000, 0), ShareInput(2, 3000, 1)], {},
        targeted_discounts=[DiscountInput(20_00, "equal")],
    )
    assert summary["expenses_cents"] == 80_00
    assert summary["people"][1]["part_cents"] == 56_00
    assert summary["people"][2]["part_cents"] == 24_00
    assert sum(person["part_cents"] for person in summary["people"].values()) == summary["net_cents"]


def test_person_discount_reduces_only_selected_person():
    summary = summarize_month(
        [100_00], [], [],
        [ShareInput(1, 5000, 0), ShareInput(2, 5000, 1)], {},
        targeted_discounts=[DiscountInput(15_00, "person", 2)],
    )
    assert summary["people"][1]["part_cents"] == 50_00
    assert summary["people"][2]["part_cents"] == 50_00
    assert summary["people"][2]["discount_cents"] == 15_00
    assert summary["people"][2]["balance_cents"] == 35_00


def test_equal_allocation_gives_residual_to_last_person():
    assert allocate_equally(100, [ShareInput(1, 5000, 0), ShareInput(2, 5000, 1), ShareInput(3, 0, 2)]) == {
        1: 33, 2: 33, 3: 34
    }


def test_period_range_can_cross_month_and_clamps_days():
    assert default_period_range("2026-03", 25, 10) == ("2026-02-25", "2026-03-10")
    assert default_period_range("2025-02", 1, 31) == ("2025-02-01", "2025-02-28")


def test_month_refers_to_previous_month_accounts():
    from app.services.periods import reference_period

    assert reference_period("2026-10") == "2026-09"
    assert reference_period("2026-01") == "2025-12"
    assert default_period_range("2026-10", 1, 31, 1) == ("2026-09-01", "2026-09-30")


def test_primary_always_paid_and_discount_becomes_extra_cost_for_others():
    summary = summarize_month(
        [300_00], [], [],
        [ShareInput(1, 3334, 0), ShareInput(2, 3333, 1), ShareInput(3, 3333, 2)], {},
        {2: -50_00},
        [DiscountInput(30_00, "person", 1), DiscountInput(10_00, "person", 2)],
        primary_id=1,
    )
    primary = summary["people"][1]
    assert primary["paid_cents"] == primary["part_cents"] and primary["balance_cents"] == 0
    assert summary["people"][2]["extra_cents"] == 15_00
    assert summary["people"][3]["extra_cents"] == 15_00
    assert summary["people"][2]["balance_cents"] == summary["people"][2]["part_cents"] + 15_00 - 10_00
    assert summary["people"][2]["accumulated_cents"] == summary["people"][2]["balance_cents"]
