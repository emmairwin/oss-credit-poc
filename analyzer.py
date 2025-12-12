"""Main analyzer orchestrator."""

import os
import sys
import json
import argparse
import time
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from github_client import GitHubClient
from ecosystems_client import EcosystemsClient
from contribution_analyzer import ContributionAnalyzer
from sponsorship_checker import SponsorshipChecker
from report_generator import ReportGenerator
from models import PackageResult, ContributionStats


def fetch_org_members(github: GitHubClient, org_name: str) -> set:
    """Fetch public members of a GitHub organization.

    Args:
        github: GitHub API client
        org_name: Organization name

    Returns:
        Set of lowercase usernames
    """
    members = set()
    try:
        members_data = github.rest_paginate(f"/orgs/{org_name}/members", max_pages=50)
        for member in members_data:
            if member and 'login' in member:
                members.add(member['login'].lower())
    except Exception as e:
        print(f"  Warning: Could not fetch org members: {e}")
    return members


def analyze_org_engagement(
    org_name: str,
    email_domain: str,
    time_window_years: int = 1,
    output_file: str = "results.json",
    max_packages: int = None,
    packages_file: str = None
):
    """Analyze organization's engagement with critical OSS packages.

    Args:
        org_name: GitHub organization name
        email_domain: Email domain for attribution
        time_window_years: Number of years to analyze (1 = past year, >1 = all time)
        output_file: Output file path
        max_packages: Maximum number of packages to analyze (for testing)
        packages_file: Optional JSON file with custom package list
    """
    load_dotenv()
    github_token = os.getenv('GITHUB_TOKEN', '').strip()
    has_valid_token = github_token.startswith(('ghp_', 'github_pat_'))

    past_year_only = (time_window_years == 1)
    time_label = "past year" if past_year_only else "all time"

    print(f"\nOSS Engagement Analysis")
    print(f"Organization: {org_name}")
    print(f"Email Domain: {email_domain}")
    print(f"Time Window: {time_label}")
    print(f"Output: {output_file}")
    print()

    ecosystems = EcosystemsClient()
    sponsorship_checker = SponsorshipChecker(ecosystems)

    org_members = set()
    github = None
    if has_valid_token:
        github = GitHubClient(github_token)
        print("Fetching organization members...")
        org_members = fetch_org_members(github, org_name)
        print(f"  Found {len(org_members)} public members")
        print()
    else:
        print("No GitHub token - issue/PR attribution will use email domain only")
        print()

    contribution_analyzer = ContributionAnalyzer(ecosystems, org_name, org_members)
    
    print("Fetching organization sponsorships...")
    org_sponsorships = sponsorship_checker.get_org_sponsorships(org_name)
    print(f"  Currently sponsoring: {len(org_sponsorships.current)} entities")
    print(f"  Previously sponsored: {len(org_sponsorships.past)} entities")
    print()
    
    if packages_file:
        print(f"Loading packages from {packages_file}...")
        try:
            with open(packages_file, 'r') as f:
                packages_data = json.load(f)
            
            # Support both array format and object with 'packages' key
            if isinstance(packages_data, dict) and 'packages' in packages_data:
                packages_data = packages_data['packages']
            
            from models import Package
            packages = []
            for pkg in packages_data:
                # Parse GitHub URL if full URL provided
                if 'repository_url' in pkg:
                    parsed = ecosystems.parse_github_url(pkg['repository_url'])
                    if parsed:
                        owner, repo = parsed
                    else:
                        continue
                elif 'owner' in pkg and 'repo' in pkg:
                    owner = pkg['owner']
                    repo = pkg['repo']
                else:
                    print(f"  Warning: Skipping package missing owner/repo: {pkg}")
                    continue
                
                packages.append(Package(
                    name=pkg.get('name', repo),
                    ecosystem=pkg.get('ecosystem', 'unknown'),
                    owner=owner,
                    repo=repo,
                    dependents_count=pkg.get('dependents_count', 0),
                    repository_url=pkg.get('repository_url', f'https://github.com/{owner}/{repo}')
                ))
            
            print(f"  Loaded {len(packages)} packages from file")
        except Exception as e:
            print(f"  Error: {e}")
            sys.exit(1)
    else:
        print("Fetching critical packages from ecosyste.ms...")
        packages = ecosystems.fetch_critical_packages()
    
    if max_packages and len(packages) > max_packages:
        print(f"  Limiting to first {max_packages} packages")
        packages = packages[:max_packages]

    print()
    print(f"Analyzing {len(packages)} packages...")
    print()
    
    results = []
    start_time = time.time()
    
    for i, package in enumerate(packages):
        print(f"[{i+1}/{len(packages)}] {package.owner}/{package.repo} ({package.ecosystem}/{package.name})")
        
        try:
            # Analyze contributions
            contributions = contribution_analyzer.analyze_contributions(
                package.owner,
                package.repo,
                email_domain,
                past_year=past_year_only
            )
            
            # Aggregate total contributions
            total = ContributionStats()
            for stats in contributions.values():
                total = total + stats
            
            # Check sponsorship
            sponsorship = sponsorship_checker.check_project_sponsorship(
                package.owner,
                package.repo,
                org_name,
                org_sponsorships
            )
            
            # Create result
            result = PackageResult(
                package=package,
                contributors=contributions,
                total_contributions=total,
                unique_contributor_count=len(contributions),
                sponsorship=sponsorship
            )
            
            results.append(result)
            
            # Print quick summary
            if result.has_contributions or result.has_active_sponsorship:
                print(f"  ✓ Contributors: {len(contributions)}, "
                      f"Commits: {total.commits}, "
                      f"PRs: {total.pull_requests_opened}, "
                      f"Sponsorship: {sponsorship.status}")
            else:
                print(f"  - No engagement")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            # Continue with next package
        
        # Progress update every 10 packages
        if (i + 1) % 10 == 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / (i + 1)
            remaining = (len(packages) - i - 1) * avg_time
            print(f"  Progress: {i+1}/{len(packages)} packages | "
                  f"Elapsed: {elapsed/60:.1f}m | "
                  f"Est. remaining: {remaining/60:.1f}m")
            github_reqs = github.request_count if github else 0
            print(f"  API requests - GitHub: {github_reqs}, ecosyste.ms: {ecosystems.request_count}")
            print()
        
        # Rate limiting - be nice to APIs
        time.sleep(0.5)
    
    print()
    print(f"Analysis complete! Total time: {(time.time() - start_time)/60:.1f} minutes")
    github_reqs = github.request_count if github else 0
    print(f"Total API requests - GitHub: {github_reqs}, ecosyste.ms: {ecosystems.request_count}")
    print()
    
    print("Generating report...")
    report = ReportGenerator.generate_report(
        results,
        org_name,
        email_domain,
        time_window_years
    )
    
    # Print summary
    ReportGenerator.print_summary(report)
    
    # Save to file
    print(f"\nSaving detailed results to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)
    
    print(f"✓ Report saved successfully!")
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze corporate engagement with critical open source packages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze an organization's engagement
  python analyzer.py --org myorg --email-domain myorg.com
  
  # Analyze over 2 years
  python analyzer.py --org myorg --email-domain myorg.com --years 2
  
  # Test with limited packages
  python analyzer.py --org myorg --email-domain myorg.com --max-packages 10
  
  # Use custom package list
  python analyzer.py --org myorg --email-domain myorg.com --packages-file my-packages.json
        """
    )
    
    parser.add_argument(
        '--org',
        required=True,
        help='GitHub organization name (e.g., "myorg")'
    )
    
    parser.add_argument(
        '--email-domain',
        required=True,
        help='Email domain for attribution (e.g., "myorg.com")'
    )
    
    parser.add_argument(
        '--years',
        type=int,
        default=1,
        help='Time window in years (default: 1)'
    )
    
    parser.add_argument(
        '--output',
        default='results.json',
        help='Output file path (default: results.json)'
    )
    
    parser.add_argument(
        '--max-packages',
        type=int,
        help='Maximum number of packages to analyze (for testing)'
    )
    
    parser.add_argument(
        '--packages-file',
        help='JSON file with custom package list (alternative to ecosyste.ms)'
    )
    
    args = parser.parse_args()
    
    try:
        analyze_org_engagement(
            org_name=args.org,
            email_domain=args.email_domain,
            time_window_years=args.years,
            output_file=args.output,
            max_packages=args.max_packages,
            packages_file=args.packages_file
        )
    except KeyboardInterrupt:
        print("\n\nAnalysis interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
