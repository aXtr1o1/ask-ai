"""
Test matrix for DashboardComposer — covers all 15 shapes from the implementation plan.
Run with: python tests/test_dashboard_composer.py
"""
import sys
sys.path.insert(0, ".")

from app.api.advance.execution_agent.output.dashboard_composer import compose

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []

def check(name, final_answer, expected_types, shape_descriptor=None):
    components = compose(final_answer, shape_descriptor)
    actual_types = [c["type"] for c in components]
    if not expected_types:
        ok = actual_types == []
    else:
        ok = all(t in actual_types for t in expected_types)
    results.append((ok, name, expected_types, actual_types, components))
    mark = PASS if ok else FAIL
    print(f"  {mark} {name}")
    if not ok:
        print(f"      expected types containing: {expected_types}")
        print(f"      actual types:              {actual_types}")
    return ok

if __name__ == "__main__":
    print("\n=== DashboardComposer Test Matrix ===\n")

    # 1. Single scalar
    check("Single scalar (int)", 42, [])

    # 2. Dict of scalars -> multiple KPI cards
    check("Dict of scalars", {"total": 200, "avg_age": 15.3, "max_age": 90}, ["kpi"])

    # 3. 2-item grouped → KPI per category + donut_chart (richer than single bar)
    check("2-item grouped_numeric (str+numeric)",
          [{"Status": "Open", "count": 120}, {"Status": "Closed", "count": 80}],
          ["kpi", "donut_chart"])

    # 4. 6-item grouped → KPI per category + donut_chart
    check("6-item grouped_numeric -> KPI+donut",
          [{"Status": s, "count": c} for s, c in [
              ("Open", 120), ("Closed", 80), ("Pending", 45),
              ("Hold", 20), ("Cancelled", 10), ("Draft", 5)
          ]],
          ["kpi", "donut_chart"])

    # 5. Time-series: date-like string key + numeric → KPIs + time_series_chart
    check("Time-series (monthly)",
          [{"month": f"2024-{m:02d}", "count": 40 + m * 3} for m in range(1, 13)],
          ["kpi", "time_series_chart"])

    # 6. Large record set — no numeric key -> table
    check("Record set — no numeric key",
          [{"Name": f"Asset-{i}", "Status": "Active", "Location": "Building A"} for i in range(50)],
          ["table"])

    # 7. Mixed dict: scalar summary + embedded list → Total KPI + KPI per dept + donut
    check("Dict with scalar + embedded list",
          {"total": 100, "groups": [{"Dept": "Mech", "count": 30}, {"Dept": "Civil", "count": 25},
                                      {"Dept": "Elec", "count": 45}]},
          ["kpi", "donut_chart"])

    # 8. None -> text
    check("None value", None, ["text"])

    # 9. Error dict -> text
    check("Error dict", {"error": "Column 'XYZ' not found"}, ["text"])

    # 10. Empty list -> text
    check("Empty list", [], ["text"])

    # 11. Scalar list -> text
    check("Scalar list", ["Active", "Open", "Pending", "Closed"], ["text"])

    # 12. List of dicts with nested objects -> table (nested serialized as JSON string)
    check("Nested objects in records",
          [{"field1": {"nested_key": "nested_val"}, "field2": 42}],
          ["record_cards"])

    # 13. Single-row dict result -> empty
    check("Single scalar from dict", {"count": 7}, [])

    # 14. Bool scalar
    check("Boolean scalar", True, [])

    # 15. Mixed list (dicts + scalars) → KPI cards + donut (richer routing)
    check("Mixed list (dicts + scalars)",
          [{"Name": "A", "count": 10}, "extra_string", {"Name": "B", "count": 20}],
          ["kpi", "donut_chart"])

    # 16. Record set dictionary wrapping metadata lists + records lists -> KPIs + table
    check("Dict wrapping metadata and records",
          {"_result_type": "record_set", "module": "assets", "total": 1,
           "fields_returned": ["AssetTagNo", "AssetBarcode"],
           "records": [{"AssetTagNo": "AAS-FF-1", "AssetBarcode": "2244402"}]},
          ["kpi", "record_cards"])

    # 17. Single scalar string
    check("Single scalar string", "Active", [])

    # 18. Small detail records list (length 5)
    check("Small detail records list (len=5)",
          [{"AssetTagNo": f"A-{i}", "Loc": "Block B"} for i in range(5)],
          ["record_cards"])

    # 19. Large detail records list (length 12)
    check("Large detail records list (len=12)",
          [{"AssetTagNo": f"A-{i}", "Loc": "Block B"} for i in range(12)],
          ["table"])

    # 20. Dict wrapping single-cell count list
    check("Dict wrapping single count row",
          {"_result_type": "record_set", "total": 1,
           "records": [{"count": 135}]},
          [])

    # 21. Medium category list (len=12) with 1 string key + 1 numeric key -> KPIs + donut + bar_chart
    check("Medium category list (len=12) grouped_numeric",
          [{"Building": f"Bld-{i}", "count": 10 + i} for i in range(12)],
          ["kpi", "donut_chart", "bar_chart"])

    print()
    passed = sum(1 for r in results if r[0])
    total  = len(results)
    print(f"  Results: {passed}/{total} passed")
    if passed < total:
        print("\n  Failed cases:")
        for ok, name, exp, act, comps in results:
            if not ok:
                print(f"    - {name}")
                print(f"      Components: {comps}")
    sys.exit(0 if passed == total else 1)
