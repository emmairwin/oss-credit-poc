"""Data models for the OSS Engagement Analyzer."""

from dataclasses import dataclass, field
from typing import Dict, Set, Optional
from datetime import datetime


@dataclass
class ContributionStats:
    """Statistics for contributions to a repository."""
    commits: int = 0
    pull_requests_opened: int = 0
    pull_requests_merged: int = 0
    issues_opened: int = 0
    issue_comments: int = 0
    pr_review_comments: int = 0
    
    def __add__(self, other):
        """Add two ContributionStats together."""
        if not isinstance(other, ContributionStats):
            return NotImplemented
        return ContributionStats(
            commits=self.commits + other.commits,
            pull_requests_opened=self.pull_requests_opened + other.pull_requests_opened,
            pull_requests_merged=self.pull_requests_merged + other.pull_requests_merged,
            issues_opened=self.issues_opened + other.issues_opened,
            issue_comments=self.issue_comments + other.issue_comments,
            pr_review_comments=self.pr_review_comments + other.pr_review_comments
        )
    
    def total_activity(self) -> int:
        """Get total number of activities."""
        return (
            self.commits + 
            self.pull_requests_opened + 
            self.issues_opened + 
            self.issue_comments + 
            self.pr_review_comments
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "commits": self.commits,
            "pull_requests_opened": self.pull_requests_opened,
            "pull_requests_merged": self.pull_requests_merged,
            "issues_opened": self.issues_opened,
            "issue_comments": self.issue_comments,
            "pr_review_comments": self.pr_review_comments,
            "total_activity": self.total_activity()
        }


@dataclass
class Package:
    """Information about a critical package."""
    name: str
    ecosystem: str
    owner: str
    repo: str
    dependents_count: int
    repository_url: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "ecosystem": self.ecosystem,
            "owner": self.owner,
            "repo": self.repo,
            "dependents_count": self.dependents_count,
            "repository_url": self.repository_url
        }


@dataclass
class SponsorshipStatus:
    """Sponsorship status for a project."""
    status: str  # ACTIVE_DIRECT, PAST_DIRECT, ACTIVE_VIA_MAINTAINER, etc.
    entity: Optional[str] = None  # The entity being sponsored
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "status": self.status,
            "entity": self.entity
        }


@dataclass
class SponsorshipData:
    """Sponsorship data for an organization."""
    current: Set[str] = field(default_factory=set)
    past: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "current": list(self.current),
            "past": list(self.past)
        }


@dataclass
class PackageResult:
    """Analysis results for a single package."""
    package: Package
    contributors: Dict[str, ContributionStats]  # email -> stats
    total_contributions: ContributionStats
    unique_contributor_count: int
    sponsorship: SponsorshipStatus
    
    @property
    def has_contributions(self) -> bool:
        """Check if package has any contributions."""
        return self.total_contributions.total_activity() > 0
    
    @property
    def has_active_sponsorship(self) -> bool:
        """Check if package has active sponsorship."""
        return "ACTIVE" in self.sponsorship.status
    
    @property
    def engagement_tier(self) -> str:
        """Determine engagement tier."""
        has_contrib = self.has_contributions
        has_sponsor = self.has_active_sponsorship
        
        if has_contrib and has_sponsor:
            return "FULL_ENGAGEMENT"
        elif has_contrib and not has_sponsor:
            return "CODE_ONLY"
        elif not has_contrib and has_sponsor:
            return "MONEY_ONLY"
        else:
            return "NO_ENGAGEMENT"
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "package": self.package.to_dict(),
            "unique_contributor_count": self.unique_contributor_count,
            "total_contributions": self.total_contributions.to_dict(),
            "sponsorship": self.sponsorship.to_dict(),
            "engagement_tier": self.engagement_tier,
            "contributors": {
                email: stats.to_dict() 
                for email, stats in self.contributors.items()
            }
        }


@dataclass
class AnalysisReport:
    """Complete analysis report."""
    summary: dict
    engagement_tiers: Dict[str, list]
    top_contributors: list
    detailed_results: list
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "summary": self.summary,
            "engagement_tiers": {
                tier: [r.to_dict() for r in results]
                for tier, results in self.engagement_tiers.items()
            },
            "top_contributors": self.top_contributors,
            "detailed_results": [r.to_dict() for r in self.detailed_results]
        }
