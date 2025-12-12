"""Contribution analyzer using ecosyste.ms APIs."""

from typing import Dict, Set
from models import ContributionStats
from ecosystems_client import EcosystemsClient


def email_matches_domain(email: str, domain: str) -> bool:
    """Check if email belongs to a domain.

    Args:
        email: Email address to check
        domain: Domain to match (e.g., 'company.com')

    Returns:
        True if email ends with @domain
    """
    if not email:
        return False

    email_lower = email.lower()

    # Skip GitHub noreply emails
    if "noreply" in email_lower and "github.com" in email_lower:
        return False

    return email_lower.endswith(f"@{domain.lower()}")


class ContributionAnalyzer:
    """Analyzes contributions using ecosyste.ms APIs."""

    def __init__(self, ecosystems_client: EcosystemsClient, org_name: str, org_members: Set[str] = None):
        """Initialize the contribution analyzer.

        Args:
            ecosystems_client: ecosyste.ms API client
            org_name: Organization name for membership checks
            org_members: Optional set of org member usernames (lowercase)
        """
        self.ecosystems = ecosystems_client
        self.org_name = org_name
        self.org_members = org_members or set()

    def set_org_members(self, members: Set[str]):
        """Set organization members for username-based attribution.

        Args:
            members: Set of usernames (will be lowercased)
        """
        self.org_members = {m.lower() for m in members}

    def analyze_contributions(
        self,
        owner: str,
        repo: str,
        email_domain: str,
        past_year: bool = True
    ) -> Dict[str, ContributionStats]:
        """Analyze contributions to a repository.

        Uses ecosyste.ms aggregated data:
        - commits.ecosyste.ms for commit counts by email
        - issues.ecosyste.ms for issue/PR counts by username

        Args:
            owner: Repository owner
            repo: Repository name
            email_domain: Email domain for attribution (e.g., 'company.com')
            past_year: If True, only count past year activity

        Returns:
            Dictionary mapping identifier to contribution stats
        """
        contributions = {}

        # Get commit data from commits.ecosyste.ms
        committers = self.ecosystems.get_repo_committers(owner, repo, past_year=past_year)

        for committer in committers:
            email = committer.get("email", "")
            count = committer.get("count", 0)

            if email_matches_domain(email, email_domain):
                if email not in contributions:
                    contributions[email] = ContributionStats()
                contributions[email].commits += count

        # Get issue/PR data from issues.ecosyste.ms
        issue_data = self.ecosystems.get_repo_issue_contributors(owner, repo)

        if past_year:
            issue_authors = issue_data.get("past_year_issue_authors", {})
            pr_authors = issue_data.get("past_year_pull_request_authors", {})
        else:
            issue_authors = issue_data.get("issue_authors", {})
            pr_authors = issue_data.get("pull_request_authors", {})

        # Attribute issues by org membership
        for username, count in issue_authors.items():
            if username.lower() in self.org_members:
                key = f"{username}@{email_domain}"
                if key not in contributions:
                    contributions[key] = ContributionStats()
                contributions[key].issues_opened += count

        # Attribute PRs by org membership
        for username, count in pr_authors.items():
            if username.lower() in self.org_members:
                key = f"{username}@{email_domain}"
                if key not in contributions:
                    contributions[key] = ContributionStats()
                contributions[key].pull_requests_opened += count

        return contributions
