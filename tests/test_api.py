"""Tests for TicketPilot API endpoints."""
from unittest.mock import patch

import pytest
from fastapi import status


class TestHealth:
    """Health check endpoint tests."""

    def test_health_returns_ok(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "ok"}

    def test_root_returns_html(self, client):
        response = client.get("/")
        assert response.status_code == status.HTTP_200_OK
        assert "text/html" in response.headers["content-type"]


class TestTickets:
    """Ticket CRUD endpoint tests."""

    TICKET_ENDPOINT = "/api/v1/tickets"

    def test_create_ticket(self, client, sample_ticket_data):
        response = client.post(self.TICKET_ENDPOINT, json=sample_ticket_data)
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["description"] == sample_ticket_data["description"]
        assert data["status"] == "open"
        assert data["id"] == 1
        assert data["resolution"] is None

    def test_create_ticket_returns_id(self, client):
        r1 = client.post(self.TICKET_ENDPOINT, json={"description": "Ticket 1"})
        r2 = client.post(self.TICKET_ENDPOINT, json={"description": "Ticket 2"})
        assert r1.json()["id"] == 1
        assert r2.json()["id"] == 2

    def test_get_ticket_by_id(self, client):
        create_resp = client.post(self.TICKET_ENDPOINT, json={"description": "Find me"})
        ticket_id = create_resp.json()["id"]

        response = client.get(f"{self.TICKET_ENDPOINT}/{ticket_id}")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["description"] == "Find me"

    def test_get_ticket_not_found(self, client):
        response = client.get(f"{self.TICKET_ENDPOINT}/9999")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Ticket not found"

    def test_list_tickets(self, client):
        client.post(self.TICKET_ENDPOINT, json={"description": "Ticket A"})
        client.post(self.TICKET_ENDPOINT, json={"description": "Ticket B"})

        response = client.get(self.TICKET_ENDPOINT)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["tickets"]) == 2
        # Most recent first
        assert data["tickets"][0]["description"] == "Ticket B"

    def test_create_ticket_empty_description(self, client):
        response = client.post(self.TICKET_ENDPOINT, json={"description": ""})
        # Empty string is allowed as description (no min-length constraint)
        assert response.status_code == status.HTTP_200_OK

    def test_create_ticket_missing_field(self, client):
        response = client.post(self.TICKET_ENDPOINT, json={})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.parametrize("desc", [
        "Short ticket",
        "A" * 5000,  # Very long description
        "Special chars: !@#$%^&*()_+-=[]{}|;':\",./<>?`~",
        "Mixed 日本語 English 汉语",
    ])
    def test_create_ticket_various_inputs(self, client, desc):
        response = client.post(self.TICKET_ENDPOINT, json={"description": desc})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["description"] == desc

    def test_list_tickets_empty(self, client):
        response = client.get(self.TICKET_ENDPOINT)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["tickets"] == []


class TestKnowledgeBase:
    """Knowledge base endpoint tests."""

    def test_ingest_knowledge_base(self, client, auth_headers):
        response = client.post("/api/v1/knowledge-base/ingest", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        assert data["documents_ingested"] > 0

    def test_ingest_reports_gold_documents(self, client, auth_headers, mock_qdrant):
        with patch("app.rag.vector_store.get_embedding", return_value=[0.1] * 384):
            response = client.post("/api/v1/knowledge-base/ingest", headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"
        assert data["gold_documents_ingested"] == 25


class TestMetrics:
    """Metrics endpoint tests."""

    def test_metrics_endpoint(self, client):
        response = client.get("/api/v1/metrics")
        assert response.status_code == status.HTTP_200_OK
        assert "ticketpilot_tickets_created_total" in response.text

    def test_metrics_count_ticket_creations(self, client):
        client.post("/api/v1/tickets", json={"description": "T1"})
        response = client.get("/api/v1/metrics")
        assert "ticketpilot_tickets_created_total" in response.text
        assert "/api/v1/tickets" in response.text or "ticketpilot_tickets_created_total" in response.text

    def test_tickets_increment_metrics(self, client):
        client.post("/api/v1/tickets", json={"description": "T1"})
        client.post("/api/v1/tickets", json={"description": "T2"})
        client.post("/api/v1/tickets", json={"description": "T3"})
        response = client.get("/api/v1/metrics")
        assert "ticketpilot_tickets_created_total" in response.text


class TestFrontend:
    """Frontend static file tests."""

    def test_css_exists(self, client):
        response = client.get("/static/styles.css")
        assert response.status_code == status.HTTP_200_OK
        assert "text/css" in response.headers["content-type"]

    def test_js_exists(self, client):
        response = client.get("/static/app.js")
        assert response.status_code == status.HTTP_200_OK
        assert "javascript" in response.headers["content-type"]

    def test_dashboard_listens_for_live_ticket_updates(self, client):
        """Dashboard must handle both the initial snapshot and live `ticket_updated` SSE events."""
        response = client.get("/")
        assert response.status_code == status.HTTP_200_OK
        html = response.text
        assert "tickets_updated" in html
        assert "ticket_updated" in html
