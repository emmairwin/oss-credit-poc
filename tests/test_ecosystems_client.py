"""Tests for EcosystemsClient sponsorship methods."""

import pytest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ecosystems_client import EcosystemsClient
from models import SponsorshipData


class TestGetAccountSponshorships:
    def test_returns_current_and_past_sponsorships(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"maintainer": {"login": "user1"}, "status": "active"},
            {"maintainer": {"login": "user2"}, "status": "active"},
            {"maintainer": {"login": "user3"}, "status": "inactive"},
        ]

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_account_sponsorships("testorg")

        assert "user1" in result.current
        assert "user2" in result.current
        assert "user3" in result.past
        assert len(result.current) == 2
        assert len(result.past) == 1

    def test_returns_empty_when_404(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_account_sponsorships("nonexistent")

        assert len(result.current) == 0
        assert len(result.past) == 0

    def test_handles_missing_maintainer_login(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"maintainer": {"login": "user1"}, "status": "active"},
            {"maintainer": {}, "status": "active"},
            {"status": "active"},
        ]

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_account_sponsorships("testorg")

        assert len(result.current) == 1
        assert "user1" in result.current


class TestGetAccountSponsors:
    def test_returns_current_and_past_sponsors(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"funder": {"login": "sponsor1"}, "status": "active"},
            {"funder": {"login": "sponsor2"}, "status": "inactive"},
        ]

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_account_sponsors("maintainer1")

        assert "sponsor1" in result.current
        assert "sponsor2" in result.past

    def test_returns_empty_when_no_sponsors(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_account_sponsors("maintainer1")

        assert len(result.current) == 0
        assert len(result.past) == 0


class TestGetRepoFunding:
    def test_returns_github_sponsors_as_list(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "metadata": {
                "funding": {
                    "github": ["sponsor1", "sponsor2"]
                }
            }
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_repo_funding("owner", "repo")

        assert result == ["sponsor1", "sponsor2"]

    def test_returns_github_sponsor_as_string_converted_to_list(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "metadata": {
                "funding": {
                    "github": "singlesponsor"
                }
            }
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_repo_funding("owner", "repo")

        assert result == ["singlesponsor"]

    def test_returns_empty_when_no_funding(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "metadata": {
                "funding": None
            }
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_repo_funding("owner", "repo")

        assert result == []

    def test_returns_empty_when_404(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_repo_funding("owner", "repo")

        assert result == []

    def test_returns_empty_when_no_github_in_funding(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "metadata": {
                "funding": {
                    "open_collective": "someproject"
                }
            }
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_repo_funding("owner", "repo")

        assert result == []


class TestUserAgent:
    def test_session_has_user_agent(self):
        client = EcosystemsClient()
        assert "User-Agent" in client.session.headers
        assert "oss-credit-analyzer" in client.session.headers["User-Agent"]


class TestGetOrgMaintainers:
    def test_returns_maintainer_usernames(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "login": "testorg",
            "maintainers": [
                {"maintainer": "User1", "count": 100},
                {"maintainer": "user2", "count": 50},
            ]
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_org_maintainers("testorg")

        assert "user1" in result
        assert "user2" in result
        assert len(result) == 2

    def test_returns_empty_when_404(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_org_maintainers("nonexistent")

        assert len(result) == 0

    def test_handles_empty_maintainers(self):
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "login": "testorg",
            "maintainers": []
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_org_maintainers("testorg")

        assert len(result) == 0


class TestRequestCount:
    def test_increments_request_count(self):
        client = EcosystemsClient()
        assert client.request_count == 0

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []

        with patch.object(client.session, 'get', return_value=mock_response):
            client.get_account_sponsorships("test")

        assert client.request_count == 1
