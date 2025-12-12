"""Client for fetching data from ecosyste.ms services."""

import requests
import re
import time
from typing import List, Optional, Set
from models import Package, SponsorshipData


class EcosystemsClient:
    """Client for interacting with ecosyste.ms APIs."""

    PACKAGES_URL = "https://packages.ecosyste.ms/api/v1"
    SPONSORS_URL = "https://sponsors.ecosyste.ms/api/v1"
    REPOS_URL = "https://repos.ecosyste.ms/api/v1"
    USER_AGENT = "oss-credit-analyzer/1.0 (emma.irwin@gmail.com)"

    def __init__(self):
        """Initialize the ecosystems client."""
        self.request_count = 0
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})
    
    @staticmethod
    def parse_github_url(url: str) -> Optional[tuple]:
        """Parse GitHub URL to extract owner and repo.
        
        Args:
            url: GitHub repository URL
            
        Returns:
            Tuple of (owner, repo) or None if not a valid GitHub URL
        """
        if not url:
            return None
        
        # Match github.com/owner/repo or github.com:owner/repo
        pattern = r'github\.com[/:]([^/]+)/([^/\.]+)'
        match = re.search(pattern, url)
        
        if match:
            owner = match.group(1)
            repo = match.group(2).replace('.git', '')
            return (owner, repo)
        return None
    
    def fetch_critical_packages(self, max_pages: int = 50) -> List[Package]:
        """Fetch critical packages from ecosyste.ms.
        
        Args:
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List of Package objects for GitHub-hosted packages
        """
        packages = []
        page = 1
        
        print("Fetching critical packages from ecosyste.ms...")
        
        while page <= max_pages:
            url = f"{self.PACKAGES_URL}/critical"
            params = {"per_page": 100, "page": page}
            
            try:
                response = self.session.get(url, params=params, timeout=30)
                self.request_count += 1

                if response.status_code != 200:
                    print(f"Error fetching page {page}: {response.status_code}")
                    break

                data = response.json()

                if not data:
                    break

                for pkg in data:
                    repo_url = pkg.get('repository_url')
                    
                    if not repo_url or 'github.com' not in repo_url:
                        continue
                    
                    parsed = self.parse_github_url(repo_url)
                    if not parsed:
                        continue
                    
                    owner, repo = parsed
                    
                    packages.append(Package(
                        name=pkg.get('name', ''),
                        ecosystem=pkg.get('ecosystem', ''),
                        owner=owner,
                        repo=repo,
                        dependents_count=pkg.get('dependent_repos_count', 0),
                        repository_url=repo_url
                    ))
                
                print(f"  Page {page}: {len(data)} packages ({len(packages)} GitHub repos so far)")
                page += 1
                
            except Exception as e:
                print(f"Error fetching critical packages: {e}")
                break
        
        print(f"Total critical packages found on GitHub: {len(packages)}")
        return packages
    
    def _paginate_sponsors_api(self, url: str, max_pages: int = 10) -> list:
        """Paginate through sponsors.ecosyste.ms API results.

        Args:
            url: Base URL to paginate
            max_pages: Maximum pages to fetch

        Returns:
            Combined list of all results
        """
        results = []
        page = 1

        while page <= max_pages:
            params = {"page": page, "per_page": 1000}

            try:
                response = self.session.get(url, params=params, timeout=30)
                self.request_count += 1

                if response.status_code == 404:
                    break

                if response.status_code != 200:
                    print(f"  Warning: sponsors API returned {response.status_code}")
                    break

                data = response.json()
                if not data:
                    break

                results.extend(data)

                if len(data) < 1000:
                    break

                page += 1
                time.sleep(0.1)

            except requests.exceptions.Timeout:
                print(f"  Warning: sponsors API timeout on page {page}")
                break
            except Exception as e:
                print(f"  Warning: sponsors API error: {e}")
                break

        return results

    def get_account_sponsorships(self, login: str) -> SponsorshipData:
        """Get entities that an account sponsors.

        Args:
            login: GitHub username or organization

        Returns:
            SponsorshipData with current and past sponsorships
        """
        url = f"{self.SPONSORS_URL}/account/{login}/sponsorships"
        sponsorships = self._paginate_sponsors_api(url)

        current = set()
        past = set()

        for item in sponsorships:
            maintainer = item.get("maintainer", {})
            maintainer_login = maintainer.get("login")

            if not maintainer_login:
                continue

            status = item.get("status", "").lower()
            if status == "active":
                current.add(maintainer_login)
            else:
                past.add(maintainer_login)

        return SponsorshipData(current=current, past=past)

    def get_account_sponsors(self, login: str) -> SponsorshipData:
        """Get sponsors of an account.

        Args:
            login: GitHub username or organization

        Returns:
            SponsorshipData with current and past sponsors
        """
        url = f"{self.SPONSORS_URL}/account/{login}/sponsors"
        sponsors = self._paginate_sponsors_api(url)

        current = set()
        past = set()

        for item in sponsors:
            funder = item.get("funder", {})
            funder_login = funder.get("login")

            if not funder_login:
                continue

            status = item.get("status", "").lower()
            if status == "active":
                current.add(funder_login)
            else:
                past.add(funder_login)

        return SponsorshipData(current=current, past=past)

    def get_repo_funding(self, owner: str, repo: str) -> list:
        """Get funding information for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            List of GitHub sponsor logins from funding config, empty if none
        """
        url = f"{self.REPOS_URL}/hosts/GitHub/repositories/{owner}%2F{repo}"

        try:
            response = self.session.get(url, timeout=30)
            self.request_count += 1

            if response.status_code != 200:
                return []

            data = response.json()
            metadata = data.get("metadata", {})
            funding = metadata.get("funding")

            if not funding:
                return []

            # funding can be a dict with 'github' key containing string or list
            github_sponsors = funding.get("github", [])

            if isinstance(github_sponsors, str):
                return [github_sponsors]
            elif isinstance(github_sponsors, list):
                return github_sponsors

            return []

        except Exception as e:
            print(f"  Warning: repos API error for {owner}/{repo}: {e}")
            return []

    def get_stats(self) -> dict:
        """Get API usage statistics.

        Returns:
            Dictionary with request count
        """
        return {"request_count": self.request_count}
