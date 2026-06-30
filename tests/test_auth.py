"""Tests for authentication and authorization endpoints."""
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import patch


class TestRegister:
    """POST /api/v1/auth/register"""

    REGISTER_URL = "/api/v1/auth/register"

    def test_register_creates_user(self, client):
        response = client.post(self.REGISTER_URL, json={
            "email": "newuser@test.com",
            "password": "secret123",
        })
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "newuser@test.com"
        assert data["user"]["role"] == "customer"
        assert data["user"]["is_active"] is True

    def test_register_duplicate_email(self, client, test_user):
        response = client.post(self.REGISTER_URL, json={
            "email": test_user.email,
            "password": "secret123",
        })
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "already exists" in response.json()["detail"]

    def test_register_short_password(self, client):
        response = client.post(self.REGISTER_URL, json={
            "email": "short@test.com",
            "password": "abc",
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_invalid_email(self, client):
        response = client.post(self.REGISTER_URL, json={
            "email": "not-an-email",
            "password": "secret123",
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLogin:
    """POST /api/v1/auth/login"""

    LOGIN_URL = "/api/v1/auth/login"

    def test_login_valid(self, client, test_user):
        response = client.post(self.LOGIN_URL, json={
            "email": "admin@test.example",
            "password": "test123",
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "admin@test.example"
        assert data["user"]["role"] == "admin"

    def test_login_wrong_password(self, client, test_user):
        response = client.post(self.LOGIN_URL, json={
            "email": "admin@test.example",
            "password": "wrongpassword",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_email(self, client):
        response = client.post(self.LOGIN_URL, json={
            "email": "nobody@test.com",
            "password": "test123",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_case_insensitive(self, client, test_user):
        """Email matching should be case-insensitive."""
        response = client.post(self.LOGIN_URL, json={
            "email": "Admin@test.example",
            "password": "test123",
        })
        assert response.status_code == status.HTTP_200_OK


class TestMe:
    """GET /api/v1/auth/me"""

    ME_URL = "/api/v1/auth/me"

    def test_me_authenticated(self, client, auth_headers):
        response = client.get(self.ME_URL, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "admin@test.example"
        assert data["role"] == "admin"

    def test_me_no_token(self, client):
        response = client.get(self.ME_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_invalid_token(self, client):
        response = client.get(self.ME_URL, headers={"Authorization": "Bearer invalidtoken"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_expired_token(self, client, test_user):
        """Token with past expiry should be rejected."""
        from app.auth.utils import create_access_token
        from datetime import timedelta
        token = create_access_token({"sub": str(test_user.id)}, expires_delta=timedelta(seconds=-1))
        response = client.get(self.ME_URL, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRBAC:
    """Role-based access control tests."""

    def test_customer_cannot_resolve_ticket(self, client, customer_headers):
        """Customers should not be able to resolve escalated tickets."""
        # Create a ticket first
        create_resp = client.post("/api/v1/tickets", json={"description": "Test ticket"})
        ticket_id = create_resp.json()["id"]

        # Try to resolve as customer
        response = client.patch(
            f"/api/v1/tickets/{ticket_id}/resolve",
            headers=customer_headers,
            json={"resolution": "Fixed!"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_customer_cannot_ingest_kb(self, client, customer_headers):
        """Customers should not be able to ingest the knowledge base."""
        response = client.post(
            "/api/v1/knowledge-base/ingest",
            headers=customer_headers,
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_customer_cannot_ingest_document(self, client, customer_headers):
        """Customers should not be able to add documents."""
        response = client.post(
            "/api/v1/documents",
            headers=customer_headers,
            json={"text": "Confidential document content"},
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_resolve_ticket(self, client, auth_headers):
        """Admin should be able to resolve an escalated ticket."""
        # Create ticket
        create_resp = client.post("/api/v1/tickets", json={"description": "Test ticket"})
        ticket_id = create_resp.json()["id"]

        # Manually set to escalated in DB for testing
        from tests.conftest import TestSessionLocal
        from app.models import Ticket, TicketStatus
        db = TestSessionLocal()
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        ticket.status = TicketStatus.ESCALATED
        db.commit()
        db.close()

        # Resolve as admin
        response = client.patch(
            f"/api/v1/tickets/{ticket_id}/resolve",
            headers=auth_headers,
            json={"resolution": "Issue resolved by admin."},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "resolved"

    def test_admin_can_ingest_kb(self, client, auth_headers):
        """Admin should be able to ingest the knowledge base."""
        response = client.post(
            "/api/v1/knowledge-base/ingest",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "success"


class TestAdminUsers:
    """Admin user management endpoints."""

    USERS_URL = "/api/v1/auth/admin/users"

    def test_list_users_admin(self, client, auth_headers, test_user):
        """Admin can list all users."""
        response = client.get(self.USERS_URL, headers=auth_headers)
        assert response.status_code == status.HTTP_200_OK
        users = response.json()
        assert len(users) >= 1
        emails = [u["email"] for u in users]
        assert test_user.email in emails

    def test_list_users_forbidden_for_customers(self, client, customer_headers):
        """Customers cannot list users."""
        response = client.get(self.USERS_URL, headers=customer_headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_change_user_role(self, client, auth_headers, customer_user):
        """Admin can change a user's role."""
        response = client.patch(
            f"{self.USERS_URL}/{customer_user.id}/role",
            headers=auth_headers,
            json={"role": "agent"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["role"] == "agent"

    def test_cannot_change_own_role(self, client, auth_headers, test_user):
        """Admin cannot change their own role."""
        response = client.patch(
            f"{self.USERS_URL}/{test_user.id}/role",
            headers=auth_headers,
            json={"role": "customer"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


class TestAnonymousTicketAccess:
    """Anonymous users should still be able to create tickets."""

    def test_anonymous_create_ticket(self, client):
        """Anonymous users can still create tickets (backward compat)."""
        response = client.post("/api/v1/tickets", json={"description": "Anonymous ticket"})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["user_id"] is None  # No user linked

    def test_anonymous_list_tickets(self, client):
        """Anonymous users can list tickets."""
        response = client.get("/api/v1/tickets")
        assert response.status_code == status.HTTP_200_OK

    def test_anonymous_get_ticket(self, client):
        """Anonymous users can get a specific ticket."""
        create_resp = client.post("/api/v1/tickets", json={"description": "Ticket"})
        ticket_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/tickets/{ticket_id}")
        assert response.status_code == status.HTTP_200_OK

    def test_authenticated_create_links_user(self, client, auth_headers, test_user):
        """Authenticated users should have their ticket linked."""
        response = client.post(
            "/api/v1/tickets",
            headers=auth_headers,
            json={"description": "My ticket"},
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["user_id"] == test_user.id

    def test_customer_sees_own_tickets_only(self, client, customer_headers, customer_user, auth_headers):
        """Customers should only see their own tickets."""
        # Create a ticket as admin
        client.post("/api/v1/tickets", headers=auth_headers, json={"description": "Admin ticket"})

        # Create a ticket as customer
        client.post("/api/v1/tickets", headers=customer_headers, json={"description": "Customer ticket"})

        # List as customer
        response = client.get("/api/v1/tickets", headers=customer_headers)
        tickets = response.json()["tickets"]
        assert len(tickets) == 1
        assert tickets[0]["description"] == "Customer ticket"
        assert tickets[0]["user_id"] == customer_user.id
