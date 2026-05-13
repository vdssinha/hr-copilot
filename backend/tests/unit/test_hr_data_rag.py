"""Unit tests for HR data RAG — full-column ingestion and role-based access control."""
import csv
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.employee import EmployeeRole
from app.services.ai.agents.hr_data_rag import (
    _row_to_text,
    ingest_hr_data,
    query_hr_data,
)


_SAMPLE_HEADERS = [
    "employee_id", "full_name", "department", "salary",
    "date_of_birth", "phone", "role", "manager_id",
]
_SAMPLE_ROWS = [
    {
        "employee_id": "E001", "full_name": "Alice", "department": "Engineering",
        "salary": "90000", "date_of_birth": "1990-01-01", "phone": "9999",
        "role": "Engineer", "manager_id": "M001",
    },
    {
        "employee_id": "E002", "full_name": "Bob", "department": "HR",
        "salary": "70000", "date_of_birth": "1985-05-05", "phone": "8888",
        "role": "HR Manager", "manager_id": "M002",
    },
]


def _make_csv(rows: list, headers: list) -> Path:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="")
    writer = csv.DictWriter(tmp, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    tmp.close()
    return Path(tmp.name)


class TestRowToText:
    def test_includes_all_fields_including_sensitive(self):
        text = _row_to_text(_SAMPLE_ROWS[0], _SAMPLE_HEADERS)
        assert "salary" in text
        assert "90000" in text
        assert "date_of_birth" in text
        assert "1990-01-01" in text
        assert "phone" in text
        assert "9999" in text

    def test_includes_safe_fields(self):
        text = _row_to_text(_SAMPLE_ROWS[0], _SAMPLE_HEADERS)
        assert "Alice" in text
        assert "Engineering" in text
        assert "E001" in text

    def test_includes_manager_id(self):
        text = _row_to_text(_SAMPLE_ROWS[0], _SAMPLE_HEADERS)
        assert "manager_id" in text
        assert "M001" in text


class TestIngestHRData:
    def test_returns_zero_for_missing_file(self):
        assert ingest_hr_data(Path("/nonexistent/file.csv")) == 0

    def test_ingests_one_doc_per_employee(self):
        csv_path = _make_csv(_SAMPLE_ROWS, _SAMPLE_HEADERS)
        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[0.1] * 10, [0.2] * 10]

        with patch("app.services.ai.agents.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_embedder", return_value=mock_embedder):
            count = ingest_hr_data(csv_path)

        assert count == 2  # one doc per employee
        mock_store.clear.assert_called_once()
        mock_store.add_documents.assert_called_once()
        Path(csv_path).unlink(missing_ok=True)

    def test_docs_include_sensitive_fields(self):
        csv_path = _make_csv(_SAMPLE_ROWS, _SAMPLE_HEADERS)
        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[0.1] * 10, [0.2] * 10]

        with patch("app.services.ai.agents.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_embedder", return_value=mock_embedder):
            ingest_hr_data(csv_path)

        stored_docs = mock_store.add_documents.call_args[0][0]
        combined = " ".join(d.content for d in stored_docs)
        assert "90000" in combined
        assert "1990-01-01" in combined
        assert "9999" in combined
        Path(csv_path).unlink(missing_ok=True)

    def test_metadata_includes_employee_id_and_manager_id(self):
        csv_path = _make_csv(_SAMPLE_ROWS, _SAMPLE_HEADERS)
        mock_store = MagicMock()
        mock_store.count.return_value = 0
        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [[0.1] * 10, [0.2] * 10]

        with patch("app.services.ai.agents.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_embedder", return_value=mock_embedder):
            ingest_hr_data(csv_path)

        stored_docs = mock_store.add_documents.call_args[0][0]
        assert stored_docs[0].metadata["employee_id"] == "E001"
        assert stored_docs[0].metadata["manager_id"] == "M001"
        assert stored_docs[1].metadata["employee_id"] == "E002"
        Path(csv_path).unlink(missing_ok=True)


class TestQueryHRDataAccessControl:
    def _make_store(self, doc_content="Alice | salary: 90000 | manager_id: M001"):
        from app.services.ai.interfaces.vector_store import Document  # interfaces stay unchanged
        mock_store = MagicMock()
        mock_store.count.return_value = 5
        doc = Document(content=doc_content, metadata={"employee_id": "E001", "manager_id": "M001"})
        mock_store.similarity_search.return_value = [(doc, 0.5)]
        return mock_store

    def _make_embedder(self):
        mock = MagicMock()
        mock.embed_query.return_value = [0.1] * 10
        return mock

    def test_employee_filtered_by_employee_id(self):
        mock_store = self._make_store()
        mock_embedder = self._make_embedder()
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Your salary is 90000."

        with patch("app.services.ai.agents.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_embedder", return_value=mock_embedder), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_llm_provider", return_value=mock_llm):
            result = query_hr_data(
                "what is my salary",
                EmployeeRole.EMPLOYEE,
                employee_code="E001",
                employee_name="Alice",
            )

        call_kwargs = mock_store.similarity_search.call_args
        where_filter = call_kwargs.kwargs.get("where") or (call_kwargs.args[2] if len(call_kwargs.args) > 2 else None)
        assert where_filter == {"employee_id": {"$eq": "E001"}}
        assert result["rows_found"] == 1

    def test_employee_no_code_returns_error(self):
        mock_store = MagicMock()
        mock_store.count.return_value = 5

        with patch("app.services.ai.agents.hr_data_rag._factory.get_vector_store", return_value=mock_store):
            result = query_hr_data("what is my salary", EmployeeRole.EMPLOYEE, employee_code="")

        assert result["rows_found"] == 0
        assert "identify" in result["answer"].lower() or "contact" in result["answer"].lower()

    def test_manager_no_where_filter(self):
        mock_store = self._make_store()
        mock_embedder = self._make_embedder()
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Direct reports: ..."

        with patch("app.services.ai.agents.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_embedder", return_value=mock_embedder), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_llm_provider", return_value=mock_llm):
            result = query_hr_data(
                "show salary for my team",
                EmployeeRole.MANAGER,
                employee_code="M001",
            )

        call_kwargs = mock_store.similarity_search.call_args
        where_filter = call_kwargs.kwargs.get("where")
        assert where_filter is None  # manager sees all records

    def test_manager_system_prompt_contains_employee_code(self):
        mock_store = self._make_store()
        mock_embedder = self._make_embedder()
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "..."

        with patch("app.services.ai.agents.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_embedder", return_value=mock_embedder), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_llm_provider", return_value=mock_llm):
            query_hr_data("list team salaries", EmployeeRole.MANAGER, employee_code="M001")

        system_arg = mock_llm.generate.call_args.kwargs.get("system", "")
        assert "M001" in system_arg
        assert "RESTRICTED" in system_arg  # prompt must mention redaction rule

    def test_admin_no_where_filter(self):
        mock_store = self._make_store()
        mock_embedder = self._make_embedder()
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "Full report."

        with patch("app.services.ai.agents.hr_data_rag._factory.get_vector_store", return_value=mock_store), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_embedder", return_value=mock_embedder), \
             patch("app.services.ai.agents.hr_data_rag._factory.get_llm_provider", return_value=mock_llm):
            result = query_hr_data("show all records", EmployeeRole.ADMIN)

        call_kwargs = mock_store.similarity_search.call_args
        where_filter = call_kwargs.kwargs.get("where")
        assert where_filter is None

    def test_empty_store_returns_not_ingested(self):
        mock_store = MagicMock()
        mock_store.count.return_value = 0

        with patch("app.services.ai.agents.hr_data_rag._factory.get_vector_store", return_value=mock_store):
            result = query_hr_data("any question", EmployeeRole.MANAGER, employee_code="M001")

        assert "not yet ingested" in result["answer"].lower()
        assert result["rows_found"] == 0
