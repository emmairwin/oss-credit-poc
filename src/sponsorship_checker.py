"""Sponsorship checker using ecosyste.ms API."""

from models import SponsorshipData, SponsorshipStatus
from ecosystems_client import EcosystemsClient


class SponsorshipChecker:
    """Checks sponsorship relationships using ecosyste.ms API."""

    def __init__(self, ecosystems_client: EcosystemsClient):
        """Initialize the sponsorship checker.

        Args:
            ecosystems_client: ecosyste.ms API client
        """
        self.ecosystems = ecosystems_client

    def get_org_sponsorships(self, org_name: str) -> SponsorshipData:
        """Get all entities sponsored by an organization.

        Args:
            org_name: Organization name

        Returns:
            SponsorshipData with current and past sponsorships
        """
        return self.ecosystems.get_account_sponsorships(org_name)

    def get_entity_sponsors(self, entity_login: str) -> SponsorshipData:
        """Get sponsors of a specific user or organization.

        Args:
            entity_login: GitHub username or organization name

        Returns:
            SponsorshipData with current and past sponsors
        """
        return self.ecosystems.get_account_sponsors(entity_login)

    def check_project_sponsorship(
        self,
        owner: str,
        repo: str,
        org_name: str,
        org_sponsorships: SponsorshipData
    ) -> SponsorshipStatus:
        """Check if organization sponsors a specific project.

        Args:
            owner: Repository owner
            repo: Repository name
            org_name: Organization name to check
            org_sponsorships: Pre-fetched organization sponsorships

        Returns:
            SponsorshipStatus indicating sponsorship state
        """
        # CHECK 1: Is repo owner directly sponsored by target org?
        if owner in org_sponsorships.current:
            return SponsorshipStatus(status="ACTIVE_DIRECT", entity=owner)
        if owner in org_sponsorships.past:
            return SponsorshipStatus(status="PAST_DIRECT", entity=owner)

        # CHECK 2: Check funding config for maintainer redirects
        github_sponsors = self.ecosystems.get_repo_funding(owner, repo)

        for target in github_sponsors:
            if target in org_sponsorships.current:
                return SponsorshipStatus(status="ACTIVE_VIA_MAINTAINER", entity=target)
            if target in org_sponsorships.past:
                return SponsorshipStatus(status="PAST_VIA_MAINTAINER", entity=target)

        # CHECK 3: Reverse lookup - check if org appears on project's sponsors
        project_sponsors = self.get_entity_sponsors(owner)

        # Case-insensitive comparison
        org_name_lower = org_name.lower()
        current_lower = {s.lower() for s in project_sponsors.current}
        past_lower = {s.lower() for s in project_sponsors.past}

        if org_name_lower in current_lower:
            return SponsorshipStatus(status="ACTIVE_CONFIRMED", entity=owner)
        if org_name_lower in past_lower:
            return SponsorshipStatus(status="PAST_CONFIRMED", entity=owner)

        return SponsorshipStatus(status="NOT_SPONSORED", entity=None)
