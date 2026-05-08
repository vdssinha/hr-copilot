"""Unit tests for HR data RAG — access control and sensitive column stripping."""
import csv
import io
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.employee import EmployeeRole
from app.services.ai.hr_data_rag import (
    _SENSITIVE_COLS,
    _rows_to_text,
    ingest_hr_data,
    query_hr_data,
)


_SAMPLE_HEADERS = ["employee_id", "full_name", "department", "salary", "date_of_birth", "phone", "role"]
_SAMPLE_ROWS = [
    {"employee_id": "E001", "full_name": "Alice", "department": "Engineering",
     "salary": "90000", "date_of_birth": "1990-01-01", "phone": "9999", "role": "Engineer"},
    {"employee_id": "E002", "full_name": "Bob", "department": "HR",
     "salary": "70000", "date_of_birth": "1985-05-05", "phone": "8888", "role": "HR Manager"},
]


def _make_csv(rows: list, headers: list) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    writer = csv.DictWriter(tmp, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    tmp.close()
    return Path(tmp.name)


class TestSensitiveColumnStripping:
    def test_sensitive_cols_defined(self):
        assert "salary" in _SENSITIVE_COLS
        assert "date_of_birth" in _SENSITIVE_COLS
        assert "phone" in _SENSITIVE_COLS

    def test_rows_to_text_excludes_sensitive(self):
        safe_headers = [h for h in _SAMPLE_HEADERS if h not in _SENSITIVE_COLS]
        text = _rows_to_text(safe_headers, _SAMPLE_ROWS)
        assert "salary" not in text
        assert "90000" not in text
        assert "1990-01-01" not in text
        assert "9999" not in text

    def test_rows_to_text_includes_safe_fields(self):
        safe_headers = [h for h in _SAMPLE_HEADERS if h not in _SENSITIVE_COLS]
        text = _rows_to_text(safe_headers, _SAMPLE_ROWS)
        assert "Alice" in text
        assert "Engineering" in text
        assert "E001" in text


class TestIngestHRData:
    def test_returns_zero_for_missing_file(self):
        count = ingest_hr_data(Path("/nonexistent/file.csv"))
        assert count == 0

    def test_ingests_batched_chunks(self):
        csv_path = _make_csv(_SAMPLE_ROWS, _SAMPLE_HEADERS)

        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[0.1] * 10]

        with patch("app.services.ai.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.hr_data_rag._factory.get_embedder", return_value=mock_embedder):
            count = ingest_hr_data(csv_path)

        assert count >= 1
        mock_store.clear.assert_called_once()
        mock_store.add_documents.assert_called_once()

        # Verify no sensitive data in stored documents
        stored_docs = mock_store.add_documents.call_args[0][0]
        for doc in stored_docs:
            assert "salary" not in doc.content.lower() or "salary:" not in doc.content.lower()
            assert "90000" not in doc.content
            assert "1990-01-01" not in doc.content

        Path(csv_path).unlink(missing_ok=True)


class TestQueryHRDataAccessControl:
    def test_employee_role_denied(self):
        result = query_hr_data("list all employees", EmployeeRole.EMPLOYEE)
        assert "denied" in result["answer"].lower() or "restricted" in result["answer"].lower()
        assert result["rows_found"] == 0

    def test_manager_allowed(self):
        mock_store = MagicMock()
        mock_store.count.return_value = 5
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 10
        mock_store.similarity_search.return_value = []

        with patch("app.services.ai.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.hr_data_rag._factory.get_embedder", return_value=mock_embedder):
            result = query_hr_data("show employees in Engineering", EmployeeRole.MANAGER)

        mock_store.similarity_search.assert_called_once()

    def test_admin_allowed(self):
        mock_store = MagicMock()
        mock_store.count.return_value = 5
        mock_embedder = MagicMock()
        mock_embedder.embed_query.return_value = [0.1] * 10
        mock_store.similarity_search.return_value = []

        with patch("app.services.ai.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.hr_data_rag._factory.get_embedder", return_value=mock_embedder):
            result = query_hr_data("show all HR records", EmployeeRole.ADMIN)

        mock_store.similarity_search.assert_called_once()

    def test_empty_store_returns_not_ingested(self):
        mock_store = MagicMock()
        mock_store.count.return_value = 0

        with patch("app.services.ai.hr_data_rag._factory.get_vector_store", return_value=mock_store):
            result = query_hr_data("any question", EmployeeRole.MANAGER)

        assert "not yet ingested" in result["answer"].lower()
        assert result["rows_found"] == 0
