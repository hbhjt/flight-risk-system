import json
import zipfile
import pytest
from ingestion.download import import_month


def test_import_preserves_provenance_and_prevents_zip_traversal(tmp_path):
    archive = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("../../synthetic.csv", "FlightDate,Origin\n2024-01-01,AAA\n")
    first = import_month(archive, "2024-01", "synthetic://unit-test", tmp_path / "raw")
    second = import_month(archive, "2024-01", "synthetic://unit-test", tmp_path / "raw")
    assert first["rows"] == 1
    assert first["retrieved_at_utc"] == second["retrieved_at_utc"]
    assert not (tmp_path / "synthetic.csv").exists()
    assert first["archive_sha256"] == second["archive_sha256"]


def test_ambiguous_archive_rejected(tmp_path):
    archive = tmp_path / "synthetic.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("a.csv", "a\n1")
        zipped.writestr("b.csv", "a\n1")
    with pytest.raises(ValueError, match="Expected one CSV"):
        import_month(archive, "2024-01", "synthetic://unit-test", tmp_path / "raw")
