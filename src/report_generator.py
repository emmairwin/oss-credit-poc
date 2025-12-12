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
            "total_issues_opened": sum(r.total_contributions.issues_opened for r in results),
            
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
        
        years = summary['time_window_years']
        time_label = "past year" if years == 1 else "all time"

        print()
        print(f"OSS Engagement: {summary['organization']}")
        print(f"Email domain: {summary['email_domain']}")
        print(f"Time window: {time_label}")
        print()
        
        print(f"Packages analyzed: {summary['total_critical_packages']}")
        print(f"  With contributions: {summary['packages_with_contributions']}")
        print(f"  With sponsorship: {summary['packages_with_active_sponsorship']}")
        print(f"  No engagement: {summary['packages_with_no_engagement']}")
        print()

        print(f"Contributions: {summary['total_commits']} commits, {summary['total_prs_opened']} PRs, {summary['total_issues_opened']} issues")
        print(f"Contributors: {summary['unique_contributors']}")
        print()
        
        if report.top_contributors:
            print("Top contributors:")
            for i, contributor in enumerate(report.top_contributors[:10], 1):
                contrib = contributor['contributions']
                print(f"  {contributor['email']}")
                print(f"    {contributor['packages_count']} packages, "
                      f"{contrib['commits']} commits, {contrib['pull_requests_opened']} PRs")
            print()

        print("Packages with contributions:")
        
        # Show packages with actual contributions
        packages_with_contribs = [
            r for r in report.detailed_results 
            if r.has_contributions
        ]
        
        if not packages_with_contribs:
            print("  (none)")
        else:
            for result in packages_with_contribs[:20]:
                pkg = result.package
                sorted_contribs = sorted(
                    result.contributors.items(),
                    key=lambda x: x[1].total_activity(),
                    reverse=True
                )
                top_email = sorted_contribs[0][0] if sorted_contribs else ""
                top_stats = sorted_contribs[0][1] if sorted_contribs else None

                details = []
                if top_stats:
                    if top_stats.commits > 0:
                        details.append(f"{top_stats.commits} commits")
                    if top_stats.pull_requests_opened > 0:
                        details.append(f"{top_stats.pull_requests_opened} PRs")

                print(f"  {pkg.owner}/{pkg.repo}: {top_email} ({', '.join(details)})")

            if len(packages_with_contribs) > 20:
                print(f"  ... and {len(packages_with_contribs) - 20} more")
        print()
