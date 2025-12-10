"""GitHub API client with REST and GraphQL support."""

import requests
import time
import json
from typing import Optional, Dict, Any, List
from datetime import datetime


class GitHubClient:
    """Client for interacting with GitHub REST and GraphQL APIs."""
    
    REST_BASE_URL = "https://api.github.com"
    GRAPHQL_URL = "https://api.github.com/graphql"
    
    def __init__(self, token: str):
        """Initialize the GitHub client.
        
        Args:
            token: GitHub personal access token
        """
        self.token = token
        self.rest_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.graphql_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        self.request_count = 0
        self.last_request_time = None
    
    def _rate_limit_wait(self, min_interval: float = 0.1):
        """Wait to respect rate limits.
        
        Args:
            min_interval: Minimum seconds between requests
        """
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
    
    def _handle_rate_limit(self, response: requests.Response) -> bool:
        """Handle rate limit responses.
        
        Args:
            response: HTTP response object
            
        Returns:
            True if request should be retried, False otherwise
        """
        if response.status_code == 403:
            # Check if it's a rate limit issue
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                if remaining == 0:
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    wait_time = max(reset_time - time.time(), 0) + 1
                    print(f"Rate limit exceeded. Waiting {wait_time:.0f} seconds...")
                    time.sleep(wait_time)
                    return True
        return False
    
    def rest_get(self, endpoint: str, params: Optional[Dict] = None, 
                 retry_count: int = 3) -> Optional[Any]:
        """Make a GET request to GitHub REST API.
        
        Args:
            endpoint: API endpoint (e.g., '/repos/owner/repo')
            params: Query parameters
            retry_count: Number of retries on failure
            
        Returns:
            JSON response data or None on error
        """
        url = f"{self.REST_BASE_URL}{endpoint}"
        
        for attempt in range(retry_count):
            self._rate_limit_wait()
            self.request_count += 1
            
            try:
                response = requests.get(url, headers=self.rest_headers, params=params)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    # Resource not found (private repo, deleted, etc.)
                    return None
                elif response.status_code == 403:
                    if self._handle_rate_limit(response):
                        continue  # Retry after waiting
                    return None
                elif response.status_code >= 500:
                    # Server error, retry
                    if attempt < retry_count - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None
                else:
                    print(f"API error {response.status_code} for {endpoint}: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"Request error for {endpoint}: {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
        
        return None
    
    def rest_paginate(self, endpoint: str, params: Optional[Dict] = None, 
                      max_pages: int = 10) -> List[Any]:
        """Paginate through REST API results.
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            max_pages: Maximum number of pages to fetch
            
        Returns:
            List of all results across pages
        """
        if params is None:
            params = {}
        
        params['per_page'] = 100
        params['page'] = 1
        
        all_results = []
        
        for page in range(1, max_pages + 1):
            params['page'] = page
            results = self.rest_get(endpoint, params)
            
            if not results:
                break
            
            if isinstance(results, list):
                if len(results) == 0:
                    break
                all_results.extend(results)
            else:
                # Single object returned
                all_results.append(results)
                break
        
        return all_results
    
    def graphql_query(self, query: str, variables: Optional[Dict] = None,
                      retry_count: int = 3) -> Optional[Dict]:
        """Execute a GraphQL query.
        
        Args:
            query: GraphQL query string
            variables: Query variables
            retry_count: Number of retries on failure
            
        Returns:
            Response data or None on error
        """
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        for attempt in range(retry_count):
            self._rate_limit_wait()
            self.request_count += 1
            
            try:
                response = requests.post(
                    self.GRAPHQL_URL,
                    headers=self.graphql_headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'errors' in data:
                        print(f"GraphQL errors: {data['errors']}")
                        return None
                    return data.get('data')
                elif response.status_code == 403:
                    if self._handle_rate_limit(response):
                        continue
                    return None
                elif response.status_code >= 500:
                    if attempt < retry_count - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return None
                else:
                    print(f"GraphQL error {response.status_code}: {response.text}")
                    return None
                    
            except Exception as e:
                print(f"GraphQL request error: {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
        
        return None
    
    def get_commits(self, owner: str, repo: str, since: str, 
                    max_pages: int = 10) -> List[Dict]:
        """Get commits for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            since: ISO 8601 timestamp
            max_pages: Maximum pages to fetch
            
        Returns:
            List of commit objects
        """
        endpoint = f"/repos/{owner}/{repo}/commits"
        params = {"since": since}
        return self.rest_paginate(endpoint, params, max_pages)
    
    def get_pulls(self, owner: str, repo: str, state: str = "all",
                  max_pages: int = 10) -> List[Dict]:
        """Get pull requests for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            state: PR state (open, closed, all)
            max_pages: Maximum pages to fetch
            
        Returns:
            List of PR objects
        """
        endpoint = f"/repos/{owner}/{repo}/pulls"
        params = {"state": state, "sort": "updated", "direction": "desc"}
        return self.rest_paginate(endpoint, params, max_pages)
    
    def get_pull_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Get commits for a specific pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            List of commit objects
        """
        endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        return self.rest_paginate(endpoint, max_pages=5)
    
    def get_issues(self, owner: str, repo: str, since: str, state: str = "all",
                   max_pages: int = 10) -> List[Dict]:
        """Get issues for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            since: ISO 8601 timestamp
            state: Issue state (open, closed, all)
            max_pages: Maximum pages to fetch
            
        Returns:
            List of issue objects
        """
        endpoint = f"/repos/{owner}/{repo}/issues"
        params = {"state": state, "since": since}
        return self.rest_paginate(endpoint, params, max_pages)
    
    def get_issue_comments(self, owner: str, repo: str, since: str,
                           max_pages: int = 10) -> List[Dict]:
        """Get issue comments for a repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            since: ISO 8601 timestamp
            max_pages: Maximum pages to fetch
            
        Returns:
            List of comment objects
        """
        endpoint = f"/repos/{owner}/{repo}/issues/comments"
        params = {"since": since}
        return self.rest_paginate(endpoint, params, max_pages)
    
    def get_pull_review_comments(self, owner: str, repo: str, since: str,
                                  max_pages: int = 10) -> List[Dict]:
        """Get pull request review comments.
        
        Args:
            owner: Repository owner
            repo: Repository name
            since: ISO 8601 timestamp
            max_pages: Maximum pages to fetch
            
        Returns:
            List of review comment objects
        """
        endpoint = f"/repos/{owner}/{repo}/pulls/comments"
        params = {"since": since, "sort": "updated", "direction": "desc"}
        return self.rest_paginate(endpoint, params, max_pages)
    
    def get_user_email(self, username: str) -> Optional[str]:
        """Get user's public email address.
        
        Args:
            username: GitHub username
            
        Returns:
            Email address or None if private
        """
        endpoint = f"/users/{username}"
        user = self.rest_get(endpoint)
        return user.get('email') if user else None
    
    def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """Get file content from repository.
        
        Args:
            owner: Repository owner
            repo: Repository name
            path: File path
            
        Returns:
            File content or None if not found
        """
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        result = self.rest_get(endpoint)
        
        if result and 'content' in result:
            import base64
            return base64.b64decode(result['content']).decode('utf-8')
        return None
    
    def get_stats(self) -> Dict[str, int]:
        """Get API usage statistics.
        
        Returns:
            Dictionary with request count
        """
        return {"request_count": self.request_count}
