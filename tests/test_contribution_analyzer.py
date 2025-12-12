"""Tests for ContributionAnalyzer using ecosyste.ms."""

import pytest
from unittest.mock import Mock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from contribution_analyzer import ContributionAnalyzer, email_matches_domain
from models import ContributionStats


class TestEmailMatchesDomain:
    def test_matches_domain(self):
        assert email_matches_domain("user@company.com", "company.com") is True

    def test_case_insensitive(self):
        assert email_matches_domain("User@COMPANY.com", "company.com") is True

    def test_no_match(self):
        assert email_matches_domain("user@other.com", "company.com") is False

    def test_empty_email(self):
        assert email_matches_domain("", "company.com") is False
        assert email_matches_domain(None, "company.com") is False

    def test_skips_github_noreply(self):
        assert email_matches_domain("user@users.noreply.github.com", "github.com") is False
        assert email_matches_domain("123+user@users.noreply.github.com", "github.com") is False
        assert email_matches_domain("noreply@github.com", "github.com") is False


class TestContributionAnalyzer:
    def setup_method(self):
        self.mock_ecosystems = Mock()
        self.org_members = {"alice", "bob"}
        self.analyzer = ContributionAnalyzer(
            self.mock_ecosystems,
            "testorg",
            self.org_members
        )

    def test_counts_commits_by_email_domain(self):
        self.mock_ecosystems.get_repo_committers.return_value = [
            {"email": "alice@company.com", "login": "alice", "count": 10},
            {"email": "bob@company.com", "login": "bob", "count": 5},
            {"email": "external@other.com", "login": "external", "count": 100},
        ]
        self.mock_ecosystems.get_repo_issue_contributors.return_value = {
            "issue_authors": {},
            "pull_request_authors": {},
            "past_year_issue_authors": {},
            "past_year_pull_request_authors": {},
        }

        result = self.analyzer.analyze_contributions("owner", "repo", "company.com")

        assert "alice@company.com" in result
        assert result["alice@company.com"].commits == 10
        assert "bob@company.com" in result
        assert result["bob@company.com"].commits == 5
        assert "external@other.com" not in result

    def test_counts_issues_by_org_membership(self):
        self.mock_ecosystems.get_repo_committers.return_value = []
        self.mock_ecosystems.get_repo_issue_contributors.return_value = {
            "issue_authors": {},
            "pull_request_authors": {},
            "past_year_issue_authors": {"alice": 3, "external": 10},
            "past_year_pull_request_authors": {},
        }

        result = self.analyzer.analyze_contributions("owner", "repo", "company.com")

        assert "alice@company.com" in result
        assert result["alice@company.com"].issues_opened == 3
        assert "external@company.com" not in result

    def test_counts_prs_by_org_membership(self):
        self.mock_ecosystems.get_repo_committers.return_value = []
        self.mock_ecosystems.get_repo_issue_contributors.return_value = {
            "issue_authors": {},
            "pull_request_authors": {},
            "past_year_issue_authors": {},
            "past_year_pull_request_authors": {"bob": 7, "external": 50},
        }

        result = self.analyzer.analyze_contributions("owner", "repo", "company.com")

        assert "bob@company.com" in result
        assert result["bob@company.com"].pull_requests_opened == 7

    def test_combines_commits_issues_prs(self):
        self.mock_ecosystems.get_repo_committers.return_value = [
            {"email": "alice@company.com", "login": "alice", "count": 10},
        ]
        self.mock_ecosystems.get_repo_issue_contributors.return_value = {
            "issue_authors": {},
            "pull_request_authors": {},
            "past_year_issue_authors": {"alice": 2},
            "past_year_pull_request_authors": {"alice": 3},
        }

        result = self.analyzer.analyze_contributions("owner", "repo", "company.com")

        assert "alice@company.com" in result
        assert result["alice@company.com"].commits == 10
        assert result["alice@company.com"].issues_opened == 2
        assert result["alice@company.com"].pull_requests_opened == 3

    def test_uses_all_time_data_when_past_year_false(self):
        self.mock_ecosystems.get_repo_committers.return_value = []
        self.mock_ecosystems.get_repo_issue_contributors.return_value = {
            "issue_authors": {"alice": 100},
            "pull_request_authors": {"alice": 50},
            "past_year_issue_authors": {"alice": 10},
            "past_year_pull_request_authors": {"alice": 5},
        }

        result = self.analyzer.analyze_contributions(
            "owner", "repo", "company.com", past_year=False
        )

        assert result["alice@company.com"].issues_opened == 100
        assert result["alice@company.com"].pull_requests_opened == 50

    def test_empty_results_when_no_matches(self):
        self.mock_ecosystems.get_repo_committers.return_value = [
            {"email": "external@other.com", "login": "external", "count": 100},
        ]
        self.mock_ecosystems.get_repo_issue_contributors.return_value = {
            "issue_authors": {},
            "pull_request_authors": {},
            "past_year_issue_authors": {"external": 10},
            "past_year_pull_request_authors": {},
        }

        result = self.analyzer.analyze_contributions("owner", "repo", "company.com")

        assert len(result) == 0

    def test_set_org_members(self):
        analyzer = ContributionAnalyzer(self.mock_ecosystems, "testorg")
        assert len(analyzer.org_members) == 0

        analyzer.set_org_members({"Alice", "BOB"})
        assert "alice" in analyzer.org_members
        assert "bob" in analyzer.org_members


class TestEcosystemsClientContributionMethods:
    def test_get_repo_committers_returns_list(self):
        from ecosystems_client import EcosystemsClient
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "committers": [
                {"name": "Alice", "email": "alice@example.com", "login": "alice", "count": 10}
            ],
            "past_year_committers": [
                {"name": "Alice", "email": "alice@example.com", "login": "alice", "count": 5}
            ]
        }

        from unittest.mock import patch
        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_repo_committers("owner", "repo", past_year=True)

        assert len(result) == 1
        assert result[0]["email"] == "alice@example.com"
        assert result[0]["count"] == 5

    def test_get_repo_committers_all_time(self):
        from ecosystems_client import EcosystemsClient
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "committers": [
                {"name": "Alice", "email": "alice@example.com", "login": "alice", "count": 100}
            ],
            "past_year_committers": []
        }

        from unittest.mock import patch
        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_repo_committers("owner", "repo", past_year=False)

        assert result[0]["count"] == 100

    def test_get_repo_issue_contributors_returns_dict(self):
        from ecosystems_client import EcosystemsClient
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "issue_authors": {"alice": 10},
            "pull_request_authors": {"bob": 5},
            "past_year_issue_authors": {"alice": 3},
            "past_year_pull_request_authors": {"bob": 2},
        }

        from unittest.mock import patch
        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.get_repo_issue_contributors("owner", "repo")

        assert result["issue_authors"]["alice"] == 10
        assert result["past_year_pull_request_authors"]["bob"] == 2

    def test_handles_404(self):
        from ecosystems_client import EcosystemsClient
        client = EcosystemsClient()

        mock_response = Mock()
        mock_response.status_code = 404

        from unittest.mock import patch
        with patch.object(client.session, 'get', return_value=mock_response):
            committers = client.get_repo_committers("owner", "repo")
            contributors = client.get_repo_issue_contributors("owner", "repo")

        assert committers == []
        assert contributors["issue_authors"] == {}
