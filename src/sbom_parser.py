"""SBOM parser for extracting package information."""

from typing import List, Optional
from dataclasses import dataclass
from lib4sbom.parser import SBOMParser
from packageurl import PackageURL


@dataclass
class SBOMPackage:
    """Package extracted from an SBOM."""
    name: str
    version: Optional[str]
    ecosystem: str
    purl: Optional[str] = None


def purl_type_to_ecosystem(purl_type: str) -> str:
    """Map purl type to ecosyste.ms registry name.

    Args:
        purl_type: Package URL type (npm, pypi, maven, etc.)

    Returns:
        ecosyste.ms registry name
    """
    mapping = {
        "npm": "npmjs.org",
        "pypi": "pypi.org",
        "gem": "rubygems.org",
        "cargo": "crates.io",
        "nuget": "nuget.org",
        "maven": "repo1.maven.org",
        "golang": "proxy.golang.org",
        "composer": "packagist.org",
        "cocoapods": "cocoapods.org",
        "hex": "hex.pm",
        "pub": "pub.dev",
    }
    return mapping.get(purl_type.lower(), purl_type)


def parse_sbom(filepath: str) -> List[SBOMPackage]:
    """Parse an SBOM file using lib4sbom.

    Args:
        filepath: Path to SBOM file (CycloneDX or SPDX in JSON, XML, YAML, etc.)

    Returns:
        List of SBOMPackage objects
    """
    parser = SBOMParser()
    parser.parse_file(filepath)

    packages = []

    for pkg_data in parser.get_packages():
        name = pkg_data.get("name")
        if not name:
            continue

        version = pkg_data.get("version")

        # Extract purl from externalreference list
        purl = None
        for ref in pkg_data.get("externalreference", []):
            if len(ref) >= 3 and ref[1] == "purl":
                purl = ref[2]
                break

        ecosystem = "unknown"

        # Try to get ecosystem from purl
        if purl:
            try:
                parsed = PackageURL.from_string(purl)
                ecosystem = purl_type_to_ecosystem(parsed.type)
                # For namespaced packages, include namespace in name
                if parsed.namespace:
                    name = f"{parsed.namespace}/{parsed.name}"
                else:
                    name = parsed.name
            except ValueError:
                pass

        packages.append(SBOMPackage(
            name=name,
            version=version,
            ecosystem=ecosystem,
            purl=purl
        ))

    return packages
