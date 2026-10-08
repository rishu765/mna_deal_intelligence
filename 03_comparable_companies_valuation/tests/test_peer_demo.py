import json

from ma_comparable_valuation.demo_peers import main


def test_peer_demo_is_offline_and_stops_before_valuation(capsys) -> None:  # type: ignore[no-untyped-def]
    main()
    output = json.loads(capsys.readouterr().out)

    assert len(output["universe"]) == 5
    assert {item["decision"] for item in output["selection"]} >= {
        "include",
        "exclude",
        "insufficient_data",
    }
    assert output["snapshots"]
    assert "No enterprise values" in output["notice"]
