"""Sponsorship checker using GitHub GraphQL API."""

import yaml
from typing import Set
from models import SponsorshipData, SponsorshipStatus
from github_client import GitHubClient


class SponsorshipChecker:
    """Checks sponsorship relationships using GitHub GraphQL API."""
    
    def __init__(self, github_client: GitHubClient):
        """Initialize the sponsorship checker.
        
        Args:
            github_client: GitHub API client
        """
        self.github = github_client
    
    def get_org_sponsorships(self, org_name: str) -> SponsorshipData:
        """Get all entities sponsored by an organization.
        
        Args:
            org_name: Organization name
            
        Returns:
            SponsorshipData with current and past sponsorships
        """
        query = """
        query($org: String!, $cursor: String) {
          organization(login: $org) {
            sponsorshipsAsSponsor(first: 100, after: $cursor) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                sponsorable {
                  ... on User { login }
                  ... on Organization { login }
                }
                isActive
              }
            }
          }
        }
        """
        
        current = set()
        past = set()
        cursor = None
        
        while True:
            variables = {"org": org_name, "cursor": cursor}
            response = self.github.graphql_query(query, variables)
            
            if not response or not response.get('organization'):
                break
            
            sponsorships = response['organization'].get('sponsorshipsAsSponsor', {})
            nodes = sponsorships.get('nodes', [])
            
            for node in nodes:
                if not node:
                    continue
                
                sponsorable = node.get('sponsorable', {})
                entity = sponsorable.get('login')
                
                if entity:
                    if node.get('isActive'):
                        current.add(entity)
                    else:
                        past.add(entity)
            
            page_info = sponsorships.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
            
            cursor = page_info.get('endCursor')
        
        return SponsorshipData(current=current, past=past)
    
    def get_entity_sponsors(self, entity_login: str) -> SponsorshipData:
        """Get sponsors of a specific user or organization.
        
        Args:
            entity_login: GitHub username or organization name
            
        Returns:
            SponsorshipData with current and past sponsors
        """
        # Try as user first
        query_user = """
        query($login: String!, $cursor: String) {
          user(login: $login) {
            sponsorshipsAsMaintainer(first: 100, after: $cursor) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                sponsorEntity {
                  ... on User { login }
                  ... on Organization { login }
                }
                isActive
              }
            }
          }
        }
        """
        
        query_org = """
        query($login: String!, $cursor: String) {
          organization(login: $login) {
            sponsorshipsAsMaintainer(first: 100, after: $cursor) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                sponsorEntity {
                  ... on User { login }
                  ... on Organization { login }
                }
                isActive
              }
            }
          }
        }
        """
        
        current = set()
        past = set()
        
        # Try user query first
        variables = {"login": entity_login, "cursor": None}
        response = self.github.graphql_query(query_user, variables)
        
        # If user not found, try as organization
        if not response or not response.get('user'):
            response = self.github.graphql_query(query_org, variables)
            maintainer_data = response.get('organization', {}).get('sponsorshipsAsMaintainer') if response else None
        else:
            maintainer_data = response['user'].get('sponsorshipsAsMaintainer')
        
        if not maintainer_data:
            return SponsorshipData(current=current, past=past)
        
        # Paginate through results
        cursor = None
        while True:
            if cursor:
                variables['cursor'] = cursor
                # Re-query with cursor
                if 'user' in (response or {}):
                    response = self.github.graphql_query(query_user, variables)
                    maintainer_data = response.get('user', {}).get('sponsorshipsAsMaintainer')
                else:
                    response = self.github.graphql_query(query_org, variables)
                    maintainer_data = response.get('organization', {}).get('sponsorshipsAsMaintainer')
                
                if not maintainer_data:
                    break
            
            nodes = maintainer_data.get('nodes', [])
            for node in nodes:
                if not node:
                    continue
                
                sponsor = node.get('sponsorEntity', {})
                sponsor_login = sponsor.get('login')
                
                if sponsor_login:
                    if node.get('isActive'):
                        current.add(sponsor_login)
                    else:
                        past.add(sponsor_login)
            
            page_info = maintainer_data.get('pageInfo', {})
            if not page_info.get('hasNextPage'):
                break
            
            cursor = page_info.get('endCursor')
        
        return SponsorshipData(current=current, past=past)
    
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
        
        # CHECK 2: Check FUNDING.yml for maintainer redirects
        try:
            funding_content = self.github.get_file_content(owner, repo, ".github/FUNDING.yml")
            
            if funding_content:
                parsed = yaml.safe_load(funding_content)
                
                if parsed and 'github' in parsed:
                    github_sponsors = parsed['github']
                    
                    # Handle both string and list formats
                    if isinstance(github_sponsors, str):
                        github_sponsors = [github_sponsors]
                    elif not isinstance(github_sponsors, list):
                        github_sponsors = []
                    
                    for target in github_sponsors:
                        if target in org_sponsorships.current:
                            return SponsorshipStatus(status="ACTIVE_VIA_MAINTAINER", entity=target)
                        if target in org_sponsorships.past:
                            return SponsorshipStatus(status="PAST_VIA_MAINTAINER", entity=target)
        except Exception:
            # No FUNDING.yml or error reading it
            pass
        
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
