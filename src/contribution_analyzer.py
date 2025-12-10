"""Contribution analyzer for tracking organization contributions."""

from typing import Dict, Set
from datetime import datetime
from models import ContributionStats
from github_client import GitHubClient


def is_org_affiliated_by_email(email: str, email_domain: str) -> bool:
    """Check if an email belongs to the organization.
    
    Args:
        email: Email address to check
        email_domain: Organization's email domain (e.g., 'microsoft.com')
        
    Returns:
        True if email belongs to organization, False otherwise
    """
def is_org_affiliated_by_email(email: str, email_domain: str) -> bool:
    """Check if an email belongs to the organization.
    
    Args:
        email: Email address to check
        email_domain: Organization's email domain (e.g., 'company.com')
        
    Returns:
        True if email belongs to organization, False otherwise
    """
    if not email or email == "":
        return False
    
    # Skip GitHub's privacy-protected noreply emails (all variants)
    # Examples: noreply@github.com, user@users.noreply.github.com, 123+user@users.noreply.github.com
    email_lower = email.lower()
    if "noreply" in email_lower and "github.com" in email_lower:
        return False
    
    # Simple domain match
    return email_lower.endswith(f"@{email_domain.lower()}")


class ContributionAnalyzer:
    """Analyzes contributions to a repository by organization members."""
    
    def __init__(self, github_client: GitHubClient, org_name: str):
        """Initialize the contribution analyzer.
        
        Args:
            github_client: GitHub API client
            org_name: Organization name for membership checks
        """
        self.github = github_client
        self.org_name = org_name
        self.user_email_cache = {}
        self.org_members_cache = None  # Lazy loaded
    
    def get_org_members(self) -> Set[str]:
        """Get all public members of the organization (cached).
        
        Returns:
            Set of usernames who are org members
        """
        if self.org_members_cache is not None:
            return self.org_members_cache
        
        print(f"Fetching members of {self.org_name} organization...")
        members = set()
        
        try:
            # Get public org members
            members_data = self.github.rest_paginate(
                f"/orgs/{self.org_name}/members",
                max_pages=50
            )
            
            for member in members_data:
                if member and 'login' in member:
                    members.add(member['login'].lower())
            
            print(f"  Found {len(members)} public org members")
        except Exception as e:
            print(f"  Warning: Could not fetch org members: {e}")
            print(f"  Will rely on email domain matching only")
        
        self.org_members_cache = members
        return members
    
    def is_org_affiliated(self, username: str, email: str, email_domain: str) -> tuple:
        """Check if user is affiliated with organization (email OR membership).
        
        Args:
            username: GitHub username
            email: Email address (may be None)
            email_domain: Organization email domain
            
        Returns:
            Tuple of (is_affiliated: bool, attribution_email: str, method: str)
            - is_affiliated: True if affiliated by email OR org membership
            - attribution_email: Email to use for grouping (username-based if no email)
            - method: 'email' or 'membership'
        """
        # TIER 1: Email domain match (most reliable)
        if is_org_affiliated_by_email(email, email_domain):
            return (True, email, 'email')
        
        # TIER 2: Organization membership (fallback)
        if username:
            org_members = self.get_org_members()
            if username.lower() in org_members:
                # Create a synthetic email for grouping
                attribution_email = f"{username}@{email_domain}"
                return (True, attribution_email, 'membership')
        
        return (False, None, None)
    
    def get_user_email(self, username: str) -> str:
        """Get user's public email with caching.
        
        Args:
            username: GitHub username
            
        Returns:
            Email address or None if private
        """
        if username in self.user_email_cache:
            return self.user_email_cache[username]
        
        email = self.github.get_user_email(username)
        self.user_email_cache[username] = email
        return email
    
    def analyze_contributions(
        self,
        owner: str,
        repo: str,
        email_domain: str,
        since_date: str
    ) -> Dict[str, ContributionStats]:
        """Analyze all contributions to a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            email_domain: Organization email domain
            since_date: ISO 8601 timestamp for start date
            
        Returns:
            Dictionary mapping email addresses to contribution statistics
        """
        contributions = {}
        
        # Parse since_date to datetime for comparison
        since_dt = datetime.fromisoformat(since_date.replace('Z', '+00:00'))
        
        # ─────────────────────────────────────────────────────────────
        # COMMITS - Use git author email (the gold standard)
        # ─────────────────────────────────────────────────────────────
        commits = self.github.get_commits(owner, repo, since_date)
        
        for commit in commits:
            if not commit.get('commit'):
                continue
            
            # Get git author info
            author_info = commit['commit'].get('author', {})
            email = author_info.get('email')
            
            # Get GitHub username from commit
            author_obj = commit.get('author', {})
            username = author_obj.get('login') if author_obj else None
            
            is_affiliated, attribution_email, method = self.is_org_affiliated(
                username, email, email_domain
            )
            
            if is_affiliated:
                if attribution_email not in contributions:
                    contributions[attribution_email] = ContributionStats()
                contributions[attribution_email].commits += 1
        
        # ─────────────────────────────────────────────────────────────
        # PULL REQUESTS - Check PR commits for email
        # ─────────────────────────────────────────────────────────────
        prs = self.github.get_pulls(owner, repo, state="all")
        counted_prs = set()  # Track which PRs we've counted per email
        
        for pr in prs:
            # Check if PR was updated in our time window
            updated_at = pr.get('updated_at')
            if updated_at:
                updated_dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                if updated_dt < since_dt:
                    break  # Sorted by updated, can stop early
            
            # Check if PR was created in our time window
            created_at = pr.get('created_at')
            if created_at:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if created_dt < since_dt:
                    continue  # Updated recently but created before window
            
            # Get commits in this PR to find author email
            pr_number = pr.get('number')
            if not pr_number:
                continue
            
            pr_commits = self.github.get_pull_commits(owner, repo, pr_number)
            
            for commit in pr_commits:
                if not commit.get('commit'):
                    continue
                
                # Get git author info
                author_info = commit['commit'].get('author', {})
                email = author_info.get('email')
                
                # Get GitHub username from commit
                author_obj = commit.get('author', {})
                username = author_obj.get('login') if author_obj else None
                
                is_affiliated, attribution_email, method = self.is_org_affiliated(
                    username, email, email_domain
                )
                
                if is_affiliated:
                    pr_key = f"{attribution_email}:{pr_number}"
                    if pr_key not in counted_prs:
                        if attribution_email not in contributions:
                            contributions[attribution_email] = ContributionStats()
                        
                        contributions[attribution_email].pull_requests_opened += 1
                        if pr.get('merged_at'):
                            contributions[attribution_email].pull_requests_merged += 1
                        
                        counted_prs.add(pr_key)
                    break  # Found affiliated author, move to next PR
        
        # ─────────────────────────────────────────────────────────────
        # ISSUES - Need user profile lookup for email
        # ─────────────────────────────────────────────────────────────
        issues = self.github.get_issues(owner, repo, since_date, state="all")
        
        for issue in issues:
            # Skip PRs (they appear in issues endpoint too)
            if issue.get('pull_request'):
                continue
            
            user = issue.get('user', {})
            username = user.get('login')
            
            if not username:
                continue
            
            user_email = self.get_user_email(username)
            
            is_affiliated, attribution_email, method = self.is_org_affiliated(
                username, user_email, email_domain
            )
            
            if is_affiliated:
                if attribution_email not in contributions:
                    contributions[attribution_email] = ContributionStats()
                contributions[attribution_email].issues_opened += 1
        
        # ─────────────────────────────────────────────────────────────
        # ISSUE COMMENTS
        # ─────────────────────────────────────────────────────────────
        comments = self.github.get_issue_comments(owner, repo, since_date)
        
        for comment in comments:
            user = comment.get('user', {})
            username = user.get('login')
            
            if not username:
                continue
            
            user_email = self.get_user_email(username)
            
            is_affiliated, attribution_email, method = self.is_org_affiliated(
                username, user_email, email_domain
            )
            
            if is_affiliated:
                if attribution_email not in contributions:
                    contributions[attribution_email] = ContributionStats()
                contributions[attribution_email].issue_comments += 1
        
        # ─────────────────────────────────────────────────────────────
        # PR REVIEW COMMENTS (code review comments)
        # ─────────────────────────────────────────────────────────────
        review_comments = self.github.get_pull_review_comments(owner, repo, since_date)
        
        for comment in review_comments:
            user = comment.get('user', {})
            username = user.get('login')
            
            if not username:
                continue
            
            user_email = self.get_user_email(username)
            
            is_affiliated, attribution_email, method = self.is_org_affiliated(
                username, user_email, email_domain
            )
            
            if is_affiliated:
                if attribution_email not in contributions:
                    contributions[attribution_email] = ContributionStats()
                contributions[attribution_email].pr_review_comments += 1
        
        return contributions
    
    def clear_cache(self):
        """Clear the user email cache."""
        self.user_email_cache.clear()
