from pathlib import Path

def test_registry_contract():
    from file_converter.core.catalog import build_catalog
    expected = Path(__file__).with_name("expected_ids.txt").read_text().splitlines()
    assert [op.id for op in build_catalog()] == expected
