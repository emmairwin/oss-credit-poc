# Corporate OSS Engagement Analyzer

A tool that measures how much a given organization contributes to and sponsors critical open source packages. Answers the question: **"Is $ORG actually supporting the OSS infrastructure they depend on?"**

## Overview

This analyzer:
- Fetches critical OSS packages from [ecosyste.ms](https://packages.ecosyste.ms/)
- Analyzes organizational contributions (commits, PRs, issues, comments) using email domain attribution
- Checks GitHub Sponsors relationships
- Generates comprehensive engagement reports

## Key Features

- **Email-based Attribution**: Uses commit author email domains to identify work done on company time
- **Multi-dimensional Analysis**: Tracks commits, PRs, issues, and review comments separately
- **Sponsorship Detection**: Checks direct sponsorship, FUNDING.yml files, and reverse lookups
- **Engagement Tiers**: Categorizes packages into Full Engagement, Code Only, Money Only, and No Engagement
- **Rate Limit Handling**: Automatic retry logic and respectful API usage

## Architecture

```
analyzer.py                    # Main CLI orchestrator
├── src/
│   ├── models.py              # Data classes (Package, ContributionStats, etc.)
│   ├── github_client.py       # GitHub REST & GraphQL API wrapper
│   ├── ecosystems_client.py   # ecosyste.ms API client
│   ├── contribution_analyzer.py  # Contribution tracking logic
│   ├── sponsorship_checker.py    # Sponsorship detection
│   └── report_generator.py       # Report generation & formatting
```

## Installation

### Prerequisites

- Python 3.8+
- GitHub Personal Access Token with scopes: `read:org`, `read:user`, `user:email`

### Setup

```bash
# Clone the repository
cd oss-credit-poc

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GITHUB_TOKEN
```

## Usage

### Quick Start (Recommended)

The easiest way to run the analyzer:

```bash
# First time setup - configure your GitHub token in .env
./run.sh

# Then run your analysis with custom package list
./run.sh --org myorg --email-domain myorg.com --packages-file example-packages.json

# Or use default (all critical packages from ecosyste.ms)
./run.sh --org myorg --email-domain myorg.com --max-packages 10
```

The `run.sh` script automatically:
- Creates the virtual environment if needed
- Installs dependencies
- Checks for GitHub token configuration
- Runs the analyzer

**Note**: On first run, the analyzer will fetch the organization's public members for the fallback attribution tier. This is a one-time fetch per analysis run.

### Manual Usage

```bash
# Activate virtual environment first
source venv/bin/activate

# Run the analyzer
python analyzer.py --org microsoft --email-domain microsoft.com
```

### Advanced Options

```bash
# Analyze over 2 years
python analyzer.py --org myorg --email-domain myorg.com --years 2

# Custom output file
python analyzer.py --org myorg --email-domain myorg.com --output myorg-report.json

# Test with limited packages from default feed
python analyzer.py --org myorg --email-domain myorg.com --max-packages 10

# Use custom package list (recommended for focused analysis)
python analyzer.py --org myorg --email-domain myorg.com --packages-file my-packages.json

# Or use python3 directly without activating venv
venv/bin/python analyzer.py --org myorg --email-domain myorg.com --max-packages 10
```

### CLI Arguments

- `--org` (required): GitHub organization name
- `--email-domain` (required): Email domain for contribution attribution (e.g., "myorg.com")
- `--years`: Time window in years (default: 1)
- `--output`: Output JSON file path (default: results.json)
- `--max-packages`: Limit number of packages analyzed (for testing)
- `--packages-file`: JSON file with custom package list (alternative to ecosyste.ms)

### Custom Package Lists

Instead of using the default critical packages from ecosyste.ms (4000+ packages), you can provide a focused list of packages you care about:

**Why use custom lists?**
- Focus on packages you actually depend on
- Analyze community-driven projects (not big tech owned)
- Faster analysis (fewer API calls)
- Track specific ecosystems (e.g., only Python, only npm)

**JSON Format:**

```json
[
  {
    "name": "requests",
    "ecosystem": "pypi",
    "owner": "psf",
    "repo": "requests",
    "dependents_count": 500000,
    "repository_url": "https://github.com/psf/requests"
  },
  {
    "name": "curl",
    "ecosystem": "other",
    "owner": "curl",
    "repo": "curl"
  },
  {
    "repository_url": "https://github.com/numpy/numpy"
  }
]
```

**Minimal format** (just owner/repo):
```json
[
  {"owner": "psf", "repo": "requests"},
  {"owner": "curl", "repo": "curl"},
  {"owner": "numpy", "repo": "numpy"}
]
```

**Finding non-big-tech packages:**
- Avoid: Big tech owned repos (check repo ownership carefully)
- Focus on: Community foundations (Apache, Python Software Foundation, CNCF)
- Individual maintainers
- Small organizations
- Critical infrastructure (curl, openssl, sqlite, etc.)

## How It Works

### 1. Email Domain Attribution

**Two-tier attribution approach:**

**Tier 1: Email Domain Match (Primary)**
- Uses commit author email domains to identify work done on company time
- Example: `alice@company.com` matches domain `company.com`
- Immutable record in git history
- Most reliable attribution method

**Tier 2: Organization Membership (Fallback)**
- Checks if GitHub username is a public member of the organization
- Used when email is private/null or uses noreply@github.com
- Creates synthetic email (`username@company.com`) for grouping
- Catches contributors with privacy-enabled emails

**Why this approach?**
- Maximizes coverage while maintaining accuracy
- Email domain proves company time (highest confidence)
- Org membership catches privacy-enabled contributors
- No manual mapping or guesswork required

**Tradeoff**: Still may miss employees using personal emails on personal time, but that's arguably personal contribution anyway.

### 2. Contribution Types Tracked

| Type | Source | Email Source |
|------|--------|--------------|
| Commits | `/repos/{owner}/{repo}/commits` | Git author email (gold standard) |
| Pull Requests | `/repos/{owner}/{repo}/pulls` | PR commit author emails |
| Issues | `/repos/{owner}/{repo}/issues` | User profile email (may be private) |
| Issue Comments | `/repos/{owner}/{repo}/issues/comments` | User profile email |
| PR Review Comments | `/repos/{owner}/{repo}/pulls/comments` | User profile email |

### 3. Sponsorship Detection

Three-tier check:
1. **Direct sponsorship**: Is repo owner in org's sponsorship list?
2. **FUNDING.yml**: Check for maintainer redirects
3. **Reverse lookup**: Query repo owner's sponsors via GraphQL

### 4. Engagement Tiers

- **FULL_ENGAGEMENT**: Contributing code AND sponsoring
- **CODE_ONLY**: Contributing but not sponsoring
- **MONEY_ONLY**: Sponsoring but not contributing
- **NO_ENGAGEMENT**: Neither

## Output Format

The tool generates a JSON report with:

```json
{
  "summary": {
    "organization": "myorg",
    "email_domain": "myorg.com",
    "time_window_years": 1,
    "total_critical_packages": 1247,
    "packages_with_contributions": 89,
    "packages_with_active_sponsorship": 12,
    "total_commits": 4521,
    "unique_contributors": 156,
    "engagement_breakdown": {
      "full_engagement": 8,
      "code_only": 81,
      "money_only": 4,
      "no_engagement": 1154
    }
  },
  "engagement_tiers": {
    "FULL_ENGAGEMENT": [...],
    "CODE_ONLY": [...],
    "MONEY_ONLY": [...],
    "NO_ENGAGEMENT": [...]
  },
  "top_contributors": [
    {
      "email": "alice@company.com",
      "packages_count": 23,
      "packages": ["requests", "numpy", ...],
      "contributions": {...}
    }
  ],
  "detailed_results": [...]
}
```

## Performance & Rate Limits

### API Usage Estimates

- **GitHub REST API**: 5,000 requests/hour (authenticated)
- **GitHub GraphQL**: 5,000 points/hour
- **Per-package estimate**: ~10-20 API calls

With 1,000+ critical packages, expect **2-4 hours** runtime with rate limiting.

### Optimization Tips

1. Use `--max-packages` for quick tests
2. Run during low-activity hours
3. Consider multiple API tokens for parallel execution (not implemented)

## Edge Cases Handled

- ✅ Archived repositories (404/403 responses)
- ✅ Empty repositories
- ✅ Private repositories in critical list
- ✅ Users with private emails
- ✅ Bot accounts
- ✅ Rate limit exceeded (automatic backoff)
- ✅ Organizations without GitHub Sponsors

## Future Enhancements

- [ ] Multiple email domains per org
- [ ] Foundation membership detection (OpenSSF, CNCF, Apache)
- [ ] Open Collective sponsorship
- [ ] Dependency graph integration
- [ ] Weighted scoring system
- [ ] HTML/CSV report output
- [ ] Parallel analysis with multiple tokens

## Contributing

This is a proof-of-concept tool. Contributions welcome!

## License

MIT License - see LICENSE file

## Credits

- Critical package data: [ecosyste.ms](https://packages.ecosyste.ms/)
- Built with GitHub REST & GraphQL APIs
