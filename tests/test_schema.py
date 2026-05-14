import sqlite3
import pytest
from src.schema import init_db, drop_all


@pytest.fixture
def conn(tmp_path):
    c = init_db(tmp_path / "test.sqlite")
    yield c
    c.close()


class TestInitDb:
    def test_all_tables_created(self, conn):
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        for name in ["books", "terms", "occurrences", "candidates",
                     "chapters", "references", "term_chapters"]:
            assert name in tables

    def test_foreign_keys_enabled(self, conn):
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    def test_books_insert_and_query(self, conn):
        conn.execute(
            "INSERT INTO books(key, title, author, year) VALUES (?,?,?,?)",
            ("test2020", "Test Book", "Author A", 2020),
        )
        conn.commit()
        row = conn.execute("SELECT title FROM books WHERE key='test2020'").fetchone()
        assert row[0] == "Test Book"

    def test_terms_unique_constraint(self, conn):
        conn.execute("INSERT INTO terms(term, n_books) VALUES ('hippocampus', 2)")
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO terms(term, n_books) VALUES ('hippocampus', 1)")

    def test_idempotent_init(self, tmp_path):
        db = tmp_path / "idem.sqlite"
        c1 = init_db(db)
        c1.close()
        c2 = init_db(db)
        tables = {r[0] for r in c2.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert "terms" in tables
        c2.close()


class TestDropAll:
    def test_removes_all_tables(self, conn):
        drop_all(conn)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert len(tables) == 0

    def test_idempotent_drop(self, conn):
        drop_all(conn)
        drop_all(conn)  # second drop should not raise
