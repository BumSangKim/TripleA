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
    from api import db as api_db
    api_db.DB_PATH = db_path
    api_db.ensure_dashboard_tables()

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


class TestModes:
    def test_modes_endpoint_lists_supported_modes(self, client):
        res = client.get("/api/modes")
        assert res.status_code == 200
        modes = {item["mode"] for item in res.json()}
        assert {"mock", "test", "backtest", "paper", "live"}.issubset(modes)

    def test_dashboard_summary_accepts_mode(self, client):
        res = client.get("/api/dashboard/summary?mode=paper")
        assert res.status_code == 200
        data = res.json()
        assert data["mode"] == "paper"
        assert data["modeInfo"]["provider"] == "PaperTradingProvider"

    def test_read_only_modes_reject_csv_upload(self, client):
        res = client.post(
            "/api/accounts/upload-csv?mode=mock",
            files={"file": ("holdings.csv", b"ticker,name,quantity,avg_price,current_price\n005930,Samsung,1,70000,71000\n")},
        )
        assert res.status_code == 403

    def test_unimplemented_provider_sync_returns_501(self, client):
        res = client.post("/api/providers/mock/sync-accounts")
        assert res.status_code == 501

    def test_provider_sync_config_error_is_structured(self, client, monkeypatch):
        from api import main as api_main
        from api.kis import KISConfigError

        class FailingProvider:
            def sync_accounts(self, conn):
                raise KISConfigError("raw app secret message")

        monkeypatch.setattr(api_main.provider_router, "get", lambda mode: FailingProvider())

        res = client.post("/api/providers/paper/sync-accounts")

        assert res.status_code == 503
        detail = res.json()["detail"]
        assert detail["code"] == "KIS_CONFIG_MISSING"
        assert detail["message"] == "KIS 계좌 동기화 설정이 누락되었습니다."
        assert "secret" not in detail["message"].lower()
        assert "secret" not in detail["userAction"].lower()


class TestAccountModeFeatures:
    def test_account_policies_are_seeded(self, client):
        res = client.get("/api/account-policies")
        assert res.status_code == 200
        policies = {p["accountType"]: p for p in res.json()}
        assert policies["ISA"]["role"] == "TAX_ADVANTAGED"
        assert policies["IRP"]["role"] == "RETIREMENT"

    def test_manual_snapshot_paper_mode_updates_account(self, client, test_db):
        conn = sqlite3.connect(test_db)
        cur = conn.execute("""
            INSERT INTO accounts
            (name, type, account_type, broker, initial_value)
            VALUES ('테스트 ISA', 'ISA', 'ISA', 'KIS', 0)
        """)
        account_id = cur.lastrowid
        conn.commit()
        conn.close()

        payload = {
            "totalValue": 21846000,
            "cashValue": 1000000,
            "domesticStockValue": 7000000,
            "foreignStockValue": 5000000,
            "bondValue": 3000000,
            "etfValue": 2000000,
            "snapshotAt": "2026-05-22T09:00:00+09:00",
        }
        res = client.post(
            f"/api/accounts/{account_id}/manual-snapshot?mode=paper",
            json=payload,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["accountId"] == account_id
        assert body["totalValue"] == 21846000

        accounts = client.get("/api/accounts?mode=paper").json()
        saved = next(a for a in accounts if a["id"] == account_id)
        assert saved["value"] == 21846000
        assert saved["dataSource"] == "MANUAL"

    def test_manual_snapshot_mock_mode_is_read_only(self, client):
        res = client.post(
            "/api/accounts/1/manual-snapshot?mode=mock",
            json={"totalValue": 1000},
        )
        assert res.status_code == 403

    def test_rebalancing_inclusion_can_be_toggled_in_paper_mode(self, client, test_db):
        conn = sqlite3.connect(test_db)
        cur = conn.execute("""
            INSERT INTO accounts
            (name, type, account_type, include_in_rebalancing)
            VALUES ('토글 계좌', '일반', 'GENERAL', 1)
        """)
        account_id = cur.lastrowid
        conn.commit()
        conn.close()

        res = client.patch(f"/api/accounts/{account_id}/rebalancing-inclusion?mode=paper&include=false")

        assert res.status_code == 200
        assert res.json()["include"] is False

    def test_rebalancing_run_records_results(self, client):
        res = client.post("/api/rebalancing/run?mode=paper")
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["mode"] == "paper"
        assert body["saved"] == len(body["results"])

        results = client.get("/api/rebalancing/results?mode=paper").json()
        assert len(results) >= body["saved"]


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

    def test_telegram_notify_records_dedup_logs(self, client, test_db, monkeypatch):
        import requests

        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1234")
        posted = []

        class DummyResponse:
            def raise_for_status(self):
                return None

        def fake_post(url, json, timeout):
            posted.append({"url": url, "json": json, "timeout": timeout})
            return DummyResponse()

        monkeypatch.setattr(requests, "post", fake_post)
        conn = sqlite3.connect(test_db)
        conn.execute("UPDATE dashboard_alerts SET is_read=1")
        conn.execute("DELETE FROM notification_logs")
        conn.execute("""
            INSERT INTO dashboard_alerts (level, category, title, message, is_read)
            VALUES ('danger', 'target', '중복 방지 테스트', '현금 부족', 0)
        """)
        conn.commit()
        conn.close()

        first = client.post("/api/alerts/notify/telegram?level_filter=danger")
        second = client.post("/api/alerts/notify/telegram?level_filter=danger")

        assert first.status_code == 200
        assert first.json()["sent"] == 1
        assert second.status_code == 200
        assert second.json()["sent"] == 0
        assert second.json()["skipped"] == 1
        assert len(posted) == 1

        conn = sqlite3.connect(test_db)
        logs = conn.execute(
            "SELECT channel_type, status, dedup_key, message FROM notification_logs"
        ).fetchall()
        conn.close()
        assert len(logs) == 1
        assert logs[0] == (
            "TELEGRAM",
            "SENT",
            logs[0][2],
            "중복 방지 테스트\n현금 부족",
        )
        assert "중복 방지 테스트" in logs[0][2]

    def test_telegram_notify_masks_token_on_failure(self, client, test_db, monkeypatch):
        import requests

        token = "secret-token-for-test"
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "1234")

        def fake_post(url, json, timeout):
            raise requests.RequestException(f"{url} failed")

        monkeypatch.setattr(requests, "post", fake_post)
        conn = sqlite3.connect(test_db)
        conn.execute("UPDATE dashboard_alerts SET is_read=1")
        conn.execute("DELETE FROM notification_logs")
        conn.execute("""
            INSERT INTO dashboard_alerts (level, category, title, message, is_read)
            VALUES ('danger', 'target', '마스킹 테스트', '토큰 보호', 0)
        """)
        conn.commit()
        conn.close()

        res = client.post("/api/alerts/notify/telegram?level_filter=danger")

        assert res.status_code == 502
        assert token not in res.json()["detail"]
        assert "***" in res.json()["detail"]

        conn = sqlite3.connect(test_db)
        log = conn.execute(
            "SELECT status, error_message FROM notification_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        assert log[0] == "FAILED"
        assert token not in log[1]
        assert "***" in log[1]


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
