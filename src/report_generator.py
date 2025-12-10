"""Report generator for OSS engagement analysis."""

from typing import List, Dict
from datetime import datetime
from models import PackageResult, AnalysisReport, ContributionStats


class ReportGenerator:
    """Generates analysis reports from package results."""
    
    @staticmethod
    def generate_report(
        results: List[PackageResult],
        org_name: str,
        email_domain: str,
        time_window_years: int
    ) -> AnalysisReport:
        """Generate comprehensive analysis report.
        
        Args:
            results: List of package analysis results
            org_name: Organization name
            email_domain: Email domain used for attribution
            time_window_years: Analysis time window
            
        Returns:
            Complete analysis report
        """
        # Categorize by engagement tier
        tiers = {
            "FULL_ENGAGEMENT": [],
            "CODE_ONLY": [],
            "MONEY_ONLY": [],
            "NO_ENGAGEMENT": []
        }
        
        for r in results:
            tiers[r.engagement_tier].append(r)
        
        # Aggregate contributor statistics
        all_contributors = {}  # email -> {packages: [], total_stats: ContributionStats}
        
        for r in results:
            for email, stats in r.contributors.items():
                if email not in all_contributors:
                    all_contributors[email] = {
                        "packages": [],
                        "total_stats": ContributionStats()
                    }
                all_contributors[email]["packages"].append(r.package.name)
                all_contributors[email]["total_stats"] = (
                    all_contributors[email]["total_stats"] + stats
                )
        
        # Sort contributors by number of packages contributed to
        top_contributors = sorted(
            all_contributors.items(),
            key=lambda x: len(x[1]["packages"]),
            reverse=True
        )[:20]
        
        # Format top contributors for output
        top_contributors_list = [
            {
                "email": email,
                "packages_count": len(data["packages"]),
                "packages": data["packages"],
                "contributions": data["total_stats"].to_dict()
            }
            for email, data in top_contributors
        ]
        
        # Calculate summary statistics
        summary = {
            "organization": org_name,
            "email_domain": email_domain,
            "time_window_years": time_window_years,
            "analysis_date": datetime.utcnow().isoformat() + "Z",
            
            "total_critical_packages": len(results),
            "packages_with_contributions": len([r for r in results if r.has_contributions]),
            "packages_with_active_sponsorship": len([r for r in results if r.has_active_sponsorship]),
            "packages_with_past_sponsorship": len([
                r for r in results 
                if "PAST" in r.sponsorship.status and not r.has_active_sponsorship
            ]),
            "packages_with_no_engagement": len(tiers["NO_ENGAGEMENT"]),
            
            "total_commits": sum(r.total_contributions.commits for r in results),
            "total_prs_opened": sum(r.total_contributions.pull_requests_opened for r in results),
            "total_prs_merged": sum(r.total_contributions.pull_requests_merged for r in results),
            "total_issues_opened": sum(r.total_contributions.issues_opened for r in results),
            "total_issue_comments": sum(r.total_contributions.issue_comments for r in results),
            "total_pr_review_comments": sum(r.total_contributions.pr_review_comments for r in results),
            
            "unique_contributors": len(all_contributors),
            
            "engagement_breakdown": {
                "full_engagement": len(tiers["FULL_ENGAGEMENT"]),
                "code_only": len(tiers["CODE_ONLY"]),
                "money_only": len(tiers["MONEY_ONLY"]),
                "no_engagement": len(tiers["NO_ENGAGEMENT"])
            }
        }
        
        return AnalysisReport(
            summary=summary,
            engagement_tiers=tiers,
            top_contributors=top_contributors_list,
            detailed_results=results
        )
    
    @staticmethod
    def print_summary(report: AnalysisReport):
        """Print a human-readable summary of the report.
        
        Args:
            report: Analysis report to summarize
        """
        summary = report.summary
        
        print("\n" + "=" * 70)
        print(f"OSS ENGAGEMENT ANALYSIS: {summary['organization']}")
        print("=" * 70)
        print(f"Email Domain: {summary['email_domain']}")
        print(f"Time Window: {summary['time_window_years']} year(s)")
        print(f"Analysis Date: {summary['analysis_date']}")
        print()
        
        print("PACKAGE STATISTICS")
        print("-" * 70)
        print(f"Total Critical Packages Analyzed: {summary['total_critical_packages']}")
        print(f"Packages with Contributions: {summary['packages_with_contributions']}")
        print(f"Packages with Active Sponsorship: {summary['packages_with_active_sponsorship']}")
        print(f"Packages with Past Sponsorship: {summary['packages_with_past_sponsorship']}")
        print(f"Packages with No Engagement: {summary['packages_with_no_engagement']}")
        print()
        
        print("ENGAGEMENT BREAKDOWN")
        print("-" * 70)
        breakdown = summary['engagement_breakdown']
        print(f"Full Engagement (Code + Money): {breakdown['full_engagement']}")
        print(f"Code Only: {breakdown['code_only']}")
        print(f"Money Only: {breakdown['money_only']}")
        print(f"No Engagement: {breakdown['no_engagement']}")
        print()
        
        print("CONTRIBUTION STATISTICS")
        print("-" * 70)
        print(f"Total Commits: {summary['total_commits']}")
        print(f"Total PRs Opened: {summary['total_prs_opened']}")
        print(f"Total PRs Merged: {summary['total_prs_merged']}")
        print(f"Total Issues Opened: {summary['total_issues_opened']}")
        print(f"Total Issue Comments: {summary['total_issue_comments']}")
        print(f"Total PR Review Comments: {summary['total_pr_review_comments']}")
        print(f"Unique Contributors: {summary['unique_contributors']}")
        print()
        
        print("TOP CONTRIBUTORS (by package count)")
        print("-" * 70)
        for i, contributor in enumerate(report.top_contributors[:10], 1):
            print(f"{i}. {contributor['email']}")
            print(f"   Packages: {contributor['packages_count']}")
            contrib = contributor['contributions']
            print(f"   Total Activity: {contrib['total_activity']} "
                  f"(commits: {contrib['commits']}, PRs: {contrib['pull_requests_opened']}, "
                  f"issues: {contrib['issues_opened']})")
        
        print()
        print("DETAILED CONTRIBUTIONS BY PACKAGE")
        print("-" * 70)
        
        # Show packages with actual contributions
        packages_with_contribs = [
            r for r in report.detailed_results 
            if r.has_contributions
        ]
        
        if packages_with_contribs:
            for result in packages_with_contribs[:20]:  # Limit to first 20
                pkg = result.package
                print(f"\n{pkg.owner}/{pkg.repo} ({pkg.ecosystem})")
                print(f"  Sponsorship: {result.sponsorship.status}")
                print(f"  Contributors ({result.unique_contributor_count}):")
                
                # Sort contributors by total activity
                sorted_contribs = sorted(
                    result.contributors.items(),
                    key=lambda x: x[1].total_activity(),
                    reverse=True
                )
                
                for email, stats in sorted_contribs[:5]:  # Show top 5 per package
                    print(f"    • {email}")
                    details = []
                    if stats.commits > 0:
                        details.append(f"{stats.commits} commits")
                    if stats.pull_requests_opened > 0:
                        details.append(f"{stats.pull_requests_opened} PRs")
                    if stats.pull_requests_merged > 0:
                        details.append(f"({stats.pull_requests_merged} merged)")
                    if stats.issues_opened > 0:
                        details.append(f"{stats.issues_opened} issues")
                    if stats.issue_comments > 0:
                        details.append(f"{stats.issue_comments} comments")
                    if stats.pr_review_comments > 0:
                        details.append(f"{stats.pr_review_comments} reviews")
                    print(f"      {', '.join(details)}")
            
            if len(packages_with_contribs) > 20:
                print(f"\n  ... and {len(packages_with_contribs) - 20} more packages with contributions")
        else:
            print("  No contributions found")
        
        print("\n" + "=" * 70)
