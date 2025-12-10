"""Client for fetching critical packages from ecosyste.ms."""

import requests
import re
from typing import List, Optional
from models import Package


class EcosystemsClient:
    """Client for interacting with ecosyste.ms API."""
    
    BASE_URL = "https://packages.ecosyste.ms/api/v1"
    
    def __init__(self):
        """Initialize the ecosystems client."""
        self.request_count = 0
    
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
            url = f"{self.BASE_URL}/critical"
            params = {"per_page": 100, "page": page}
            
            try:
                response = requests.get(url, params=params)
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
    
    def get_stats(self) -> dict:
        """Get API usage statistics.
        
        Returns:
            Dictionary with request count
        """
        return {"request_count": self.request_count}
