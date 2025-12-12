"""Tests for SponsorshipChecker."""

import pytest
from unittest.mock import Mock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sponsorship_checker import SponsorshipChecker
from models import SponsorshipData, SponsorshipStatus


class TestCheckProjectSponsorship:
    def setup_method(self):
        self.mock_ecosystems = Mock()
        self.checker = SponsorshipChecker(self.mock_ecosystems)

    def test_active_direct_sponsorship(self):
        org_sponsorships = SponsorshipData(
            current={"owner1", "owner2"},
            past={"oldowner"}
        )

        result = self.checker.check_project_sponsorship(
            owner="owner1",
            repo="repo",
            org_name="myorg",
            org_sponsorships=org_sponsorships
        )

        assert result.status == "ACTIVE_DIRECT"
        assert result.entity == "owner1"

    def test_past_direct_sponsorship(self):
        org_sponsorships = SponsorshipData(
            current={"owner2"},
            past={"owner1"}
        )

        result = self.checker.check_project_sponsorship(
            owner="owner1",
            repo="repo",
            org_name="myorg",
            org_sponsorships=org_sponsorships
        )

        assert result.status == "PAST_DIRECT"
        assert result.entity == "owner1"

    def test_active_via_maintainer_from_funding(self):
        org_sponsorships = SponsorshipData(
            current={"maintainer1"},
            past=set()
        )
        self.mock_ecosystems.get_repo_funding.return_value = ["maintainer1"]
        self.mock_ecosystems.get_account_sponsors.return_value = SponsorshipData()

        result = self.checker.check_project_sponsorship(
            owner="someowner",
            repo="repo",
            org_name="myorg",
            org_sponsorships=org_sponsorships
        )

        assert result.status == "ACTIVE_VIA_MAINTAINER"
        assert result.entity == "maintainer1"

    def test_past_via_maintainer_from_funding(self):
        org_sponsorships = SponsorshipData(
            current=set(),
            past={"maintainer1"}
        )
        self.mock_ecosystems.get_repo_funding.return_value = ["maintainer1"]
        self.mock_ecosystems.get_account_sponsors.return_value = SponsorshipData()

        result = self.checker.check_project_sponsorship(
            owner="someowner",
            repo="repo",
            org_name="myorg",
            org_sponsorships=org_sponsorships
        )

        assert result.status == "PAST_VIA_MAINTAINER"
        assert result.entity == "maintainer1"

    def test_active_confirmed_via_reverse_lookup(self):
        org_sponsorships = SponsorshipData(current=set(), past=set())
        self.mock_ecosystems.get_repo_funding.return_value = []
        self.mock_ecosystems.get_account_sponsors.return_value = SponsorshipData(
            current={"MyOrg"},
            past=set()
        )

        result = self.checker.check_project_sponsorship(
            owner="someowner",
            repo="repo",
            org_name="myorg",
            org_sponsorships=org_sponsorships
        )

        assert result.status == "ACTIVE_CONFIRMED"
        assert result.entity == "someowner"

    def test_past_confirmed_via_reverse_lookup(self):
        org_sponsorships = SponsorshipData(current=set(), past=set())
        self.mock_ecosystems.get_repo_funding.return_value = []
        self.mock_ecosystems.get_account_sponsors.return_value = SponsorshipData(
            current=set(),
            past={"myorg"}
        )

        result = self.checker.check_project_sponsorship(
            owner="someowner",
            repo="repo",
            org_name="myorg",
            org_sponsorships=org_sponsorships
        )

        assert result.status == "PAST_CONFIRMED"
        assert result.entity == "someowner"

    def test_not_sponsored(self):
        org_sponsorships = SponsorshipData(current=set(), past=set())
        self.mock_ecosystems.get_repo_funding.return_value = []
        self.mock_ecosystems.get_account_sponsors.return_value = SponsorshipData()

        result = self.checker.check_project_sponsorship(
            owner="someowner",
            repo="repo",
            org_name="myorg",
            org_sponsorships=org_sponsorships
        )

        assert result.status == "NOT_SPONSORED"
        assert result.entity is None

    def test_case_insensitive_reverse_lookup(self):
        org_sponsorships = SponsorshipData(current=set(), past=set())
        self.mock_ecosystems.get_repo_funding.return_value = []
        self.mock_ecosystems.get_account_sponsors.return_value = SponsorshipData(
            current={"MYORG"},
            past=set()
        )

        result = self.checker.check_project_sponsorship(
            owner="someowner",
            repo="repo",
            org_name="myorg",
            org_sponsorships=org_sponsorships
        )

        assert result.status == "ACTIVE_CONFIRMED"


class TestGetOrgSponshorships:
    def test_delegates_to_ecosystems_client(self):
        mock_ecosystems = Mock()
        mock_ecosystems.get_account_sponsorships.return_value = SponsorshipData(
            current={"user1"},
            past={"user2"}
        )
        checker = SponsorshipChecker(mock_ecosystems)

        result = checker.get_org_sponsorships("myorg")

        mock_ecosystems.get_account_sponsorships.assert_called_once_with("myorg")
        assert "user1" in result.current
        assert "user2" in result.past


class TestGetEntitySponsors:
    def test_delegates_to_ecosystems_client(self):
        mock_ecosystems = Mock()
        mock_ecosystems.get_account_sponsors.return_value = SponsorshipData(
            current={"sponsor1"},
            past=set()
        )
        checker = SponsorshipChecker(mock_ecosystems)

        result = checker.get_entity_sponsors("maintainer1")

        mock_ecosystems.get_account_sponsors.assert_called_once_with("maintainer1")
        assert "sponsor1" in result.current
