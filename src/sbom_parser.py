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
    purl: Optional[str] = None
    ecosystem: str = "unknown"


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

        # Get clean name from purl if available
        if purl:
            try:
                parsed = PackageURL.from_string(purl)
                if parsed.namespace:
                    name = f"{parsed.namespace}/{parsed.name}"
                else:
                    name = parsed.name
            except ValueError:
                pass

        packages.append(SBOMPackage(
            name=name,
            version=version,
            purl=purl
        ))

    return packages
