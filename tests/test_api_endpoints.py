"""
tests/test_api_endpoints.py
FastAPI 엔드포인트 통합 테스트
"""
import os
import sqlite3
import tempfile
import pytest
from fastapi.testclient import TestClient


# ── 테스트용 임시 DB 설정 ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_db():
    """임시 SQLite DB를 생성하고 경로를 환경 변수로 설정"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    os.environ["DB_PATH"] = db_path

    # 테이블 초기화
    from api.db import ensure_dashboard_tables
    ensure_dashboard_tables()

    # 테스트용 지표 데이터 삽입
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS indicators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indicator TEXT, value REAL, unit TEXT, date TEXT,
            source TEXT, created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.executemany(
        "INSERT INTO indicators (indicator, value, unit, date, source) VALUES (?,?,?,?,?)",
        [
            ("CPIAUCSL", 3.4, "%", "2024-05-01", "FRED"),
            ("FEDFUNDS", 5.5, "%", "2024-05-01", "FRED"),
            ("UNRATE",   3.9, "%", "2024-05-01", "FRED"),
        ]
    )
    conn.commit()
    conn.close()

    yield db_path

    # 정리
    os.unlink(db_path)
    del os.environ["DB_PATH"]


@pytest.fixture(scope="module")
def client(test_db):
    from api.main import app
    return TestClient(app)


# ── 헬스체크 ────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_ok(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


# ── 매크로 지표 ──────────────────────────────────────────────────────

class TestMacroEndpoints:
    def test_macro_summary_returns_list(self, client):
        res = client.get("/api/macro/summary")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_macro_history_returns_list(self, client):
        res = client.get("/api/macro/history/CPIAUCSL?days=30")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_macro_history_each_has_date_value(self, client):
        res = client.get("/api/macro/history/FEDFUNDS?days=30")
        data = res.json()
        for item in data:
            assert "date" in item
            assert "value" in item


# ── 목표 관리 ────────────────────────────────────────────────────────

class TestTargetsEndpoints:
    def test_get_targets_returns_list(self, client):
        res = client.get("/api/targets")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_put_target_updates_value(self, client):
        res = client.put("/api/targets", json={
            "asset_class": "국내주식",
            "target_value": 30.0,
            "warning_thr": 5.0,
            "danger_thr": 10.0,
        })
        assert res.status_code == 200
        assert res.json()["ok"] is True

    def test_put_target_missing_field_returns_422(self, client):
        # asset_class 없이 요청 → 422
        res = client.put("/api/targets", json={"target_value": 30.0})
        assert res.status_code == 422


# ── 리밸런싱 제안 ────────────────────────────────────────────────────

class TestRebalancingEndpoint:
    def test_suggestions_returns_list(self, client):
        res = client.get("/api/rebalancing/suggestions")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_suggestions_have_required_fields(self, client):
        res = client.get("/api/rebalancing/suggestions")
        data = res.json()
        for item in data:
            assert "asset" in item
            assert "action" in item
            assert "deviation" in item


# ── 알림 ─────────────────────────────────────────────────────────────

class TestAlertsEndpoints:
    def test_get_recent_alerts_returns_list(self, client):
        res = client.get("/api/alerts/recent")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_mark_alert_read_nonexistent_still_ok(self, client):
        # 없는 ID도 200 반환 (DB update는 0건이지만 오류 아님)
        res = client.patch("/api/alerts/99999/read")
        assert res.status_code == 200

    def test_generate_alerts_endpoint(self, client):
        res = client.post("/api/alerts/generate")
        assert res.status_code == 200
        assert "created" in res.json()


# ── 자료실 ───────────────────────────────────────────────────────────

class TestDocumentsEndpoints:
    def test_list_documents_returns_list(self, client):
        res = client.get("/api/documents")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_create_document(self, client):
        payload = {"type": "memo", "title": "테스트 메모", "content": "테스트 내용", "tags": "테스트"}
        res = client.post("/api/documents", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "테스트 메모"
        assert "id" in data

    def test_created_document_appears_in_list(self, client):
        client.post("/api/documents", json={"type": "report", "title": "조회테스트"})
        res = client.get("/api/documents")
        titles = [d["title"] for d in res.json()]
        assert "조회테스트" in titles

    def test_documents_type_filter(self, client):
        client.post("/api/documents", json={"type": "memo", "title": "타입필터테스트"})
        res = client.get("/api/documents?type=memo")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        for doc in data:
            assert doc["type"] == "memo"

    def test_update_document(self, client):
        # 먼저 생성
        create_res = client.post("/api/documents", json={"type": "idea", "title": "수정전 제목", "content": "원본"})
        assert create_res.status_code == 200
        doc_id = create_res.json()["id"]
        # 수정
        update_res = client.put(f"/api/documents/{doc_id}", json={"type": "idea", "title": "수정후 제목", "content": "변경됨"})
        assert update_res.status_code == 200
        assert update_res.json()["title"] == "수정후 제목"
        assert update_res.json()["content"] == "변경됨"

    def test_update_document_not_found(self, client):
        res = client.put("/api/documents/99999", json={"type": "memo", "title": "없는문서"})
        assert res.status_code == 404

    def test_delete_document(self, client):
        # 삭제할 문서 생성
        create_res = client.post("/api/documents", json={"type": "news", "title": "삭제테스트문서"})
        doc_id = create_res.json()["id"]
        # 삭제
        del_res = client.delete(f"/api/documents/{doc_id}")
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] == doc_id
        # 삭제 후 조회 불가 확인
        list_res = client.get("/api/documents")
        ids = [d["id"] for d in list_res.json()]
        assert doc_id not in ids

    def test_delete_document_not_found(self, client):
        res = client.delete("/api/documents/99999")
        assert res.status_code == 404


# ── 검색 ─────────────────────────────────────────────────────────────

class TestSearchEndpoint:
    def test_search_empty_query_returns_empty(self, client):
        res = client.get("/api/search?q=")
        assert res.status_code == 200
        assert res.json()["results"] == []

    def test_search_returns_results(self, client):
        res = client.get("/api/search?q=CPI")
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
        assert isinstance(data["results"], list)


# ── 캘린더 ───────────────────────────────────────────────────────────

class TestCalendarEndpoint:
    def test_calendar_events_returns_list(self, client):
        res = client.get("/api/calendar/events")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


# ── 인증 ─────────────────────────────────────────────────────────────

class TestAuthEndpoint:
    def test_login_with_valid_credentials(self, client):
        res = client.post("/api/auth/token", data={
            "username": "admin", "password": "triplea123"
        })
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_login_with_invalid_credentials(self, client):
        res = client.post("/api/auth/token", data={
            "username": "admin", "password": "wrongpass"
        })
        assert res.status_code == 401


# ── 시스템 상태 ──────────────────────────────────────────────────────

class TestSystemStatusEndpoint:
    def test_system_status_returns_expected_fields(self, client):
        res = client.get("/api/system/status")
        assert res.status_code == 200
        data = res.json()
        assert "macro_last_update" in data
        assert "success_rate" in data
        assert "pipeline_status" in data
        assert "total_indicators" in data
