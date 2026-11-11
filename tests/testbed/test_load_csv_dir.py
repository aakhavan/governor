"""Generic CSV-folder loader (batch2d section 24), offline: statements and the guard, no database."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "testbed" / "sample"

_spec = importlib.util.spec_from_file_location("load_csv_dir", ROOT / "testbed" / "load_csv_dir.py")
loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(loader)


def test_loader_refuses_a_non_empty_raw_without_replace():
    with pytest.raises(loader.LoaderError, match="--replace"):
        loader.check_raw(["olist_orders_dataset"], replace=False)
    loader.check_raw(["olist_orders_dataset"], replace=True)
    loader.check_raw([], replace=False)


def test_loader_refuses_before_any_change(monkeypatch, tmp_path):
    """The guard runs before the drops and loads: a non-empty raw without --replace executes nothing else."""
    executed = []

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, stmt, params=None):
            executed.append(stmt)

            class R:
                def fetchall(self):
                    return [("old_table",)]
            return R()

    import psycopg
    monkeypatch.setattr(psycopg, "connect", lambda dsn, autocommit: Conn())
    with pytest.raises(loader.LoaderError):
        loader.load(SAMPLE, "postgresql://x", replace=False)
    assert len(executed) == 2  # CREATE SCHEMA IF NOT EXISTS raw, then the table list


def test_loader_builds_safe_statements():
    evil = 'x"; DROP SCHEMA analytics; --'
    create = loader.create_statement(evil, ["a", 'b"c']).as_string(None)
    assert create.startswith('CREATE TABLE "raw".')
    assert '"x""; DROP SCHEMA analytics; --"' in create and '"b""c" text' in create
    assert '"_loaded_at" timestamptz NOT NULL DEFAULT now()' in create
    copy = loader.copy_statement("t", ["a", "b"]).as_string(None)
    assert copy == 'COPY "raw"."t" ("a", "b") FROM STDIN WITH (FORMAT csv, HEADER true)'
    drops = [s.as_string(None) for s in loader.drop_statements(["b", "a"])]
    assert drops == ['DROP TABLE "raw"."a"', 'DROP TABLE "raw"."b"']  # raw only, never CASCADE
    assert loader.count_statement("t").as_string(None) == 'SELECT count(*) FROM "raw"."t"'


def test_loader_reads_every_csv_in_the_folder(tmp_path):
    tables = loader.read_tables(SAMPLE)
    assert len(tables) == 9 and tables["olist_orders_dataset"][0] == "order_id"
    (tmp_path / "dup.csv").write_text("a,a\n1,2\n", encoding="utf-8")
    with pytest.raises(loader.LoaderError, match="duplicate"):
        loader.read_tables(tmp_path)
    with pytest.raises(loader.LoaderError, match="no"):
        loader.read_tables(tmp_path / "empty")


def test_loader_without_dsn_exits_2(monkeypatch, capsys):
    monkeypatch.delenv("GOVERNOR_PG_DSN", raising=False)
    assert loader.main(["--source", str(SAMPLE)]) == 2
    captured = capsys.readouterr()
    assert "DSN" in captured.err and captured.out == ""
