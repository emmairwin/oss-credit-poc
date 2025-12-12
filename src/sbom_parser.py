"""SBOM parser for extracting package information."""

import json
import re
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class SBOMPackage:
    """Package extracted from an SBOM."""
    name: str
    version: Optional[str]
    ecosystem: str
    purl: Optional[str] = None


def parse_purl(purl: str) -> Optional[dict]:
    """Parse a Package URL (purl) into components.

    Args:
        purl: Package URL like pkg:npm/lodash@4.17.21

    Returns:
        Dict with type, namespace, name, version or None if invalid
    """
    if not purl or not purl.startswith("pkg:"):
        return None

    # Format: pkg:type/namespace/name@version?qualifiers#subpath
    # or: pkg:type/name@version
    match = re.match(
        r"pkg:([^/]+)/(?:([^/]+)/)?([^@?#]+)(?:@([^?#]+))?",
        purl
    )

    if not match:
        return None

    pkg_type, namespace, name, version = match.groups()

    return {
        "type": pkg_type,
        "namespace": namespace,
        "name": name,
        "version": version,
    }


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


def parse_cyclonedx(data: dict) -> List[SBOMPackage]:
    """Parse CycloneDX SBOM format.

    Args:
        data: Parsed JSON data from CycloneDX SBOM

    Returns:
        List of SBOMPackage objects
    """
    packages = []
    components = data.get("components", [])

    for component in components:
        # Skip non-library components
        comp_type = component.get("type", "library")
        if comp_type not in ("library", "framework"):
            continue

        name = component.get("name")
        if not name:
            continue

        version = component.get("version")
        purl = component.get("purl")

        # Try to get ecosystem from purl first
        ecosystem = None
        if purl:
            parsed = parse_purl(purl)
            if parsed:
                ecosystem = purl_type_to_ecosystem(parsed["type"])
                # For namespaced packages (like @scope/name in npm)
                if parsed["namespace"]:
                    name = f"{parsed['namespace']}/{parsed['name']}"
                else:
                    name = parsed["name"]

        # Fall back to bom-ref or group for ecosystem hints
        if not ecosystem:
            bom_ref = component.get("bom-ref", "")
            if "npm" in bom_ref.lower():
                ecosystem = "npmjs.org"
            elif "pypi" in bom_ref.lower():
                ecosystem = "pypi.org"
            else:
                ecosystem = "unknown"

        packages.append(SBOMPackage(
            name=name,
            version=version,
            ecosystem=ecosystem,
            purl=purl
        ))

    return packages


def parse_spdx(data: dict) -> List[SBOMPackage]:
    """Parse SPDX SBOM format (JSON).

    Args:
        data: Parsed JSON data from SPDX SBOM

    Returns:
        List of SBOMPackage objects
    """
    packages = []
    spdx_packages = data.get("packages", [])

    for pkg in spdx_packages:
        name = pkg.get("name")
        if not name:
            continue

        version = pkg.get("versionInfo")

        # Try to get ecosystem from external refs
        ecosystem = "unknown"
        purl = None

        for ref in pkg.get("externalRefs", []):
            if ref.get("referenceType") == "purl":
                purl = ref.get("referenceLocator")
                parsed = parse_purl(purl)
                if parsed:
                    ecosystem = purl_type_to_ecosystem(parsed["type"])
                    if parsed["namespace"]:
                        name = f"{parsed['namespace']}/{parsed['name']}"
                    else:
                        name = parsed["name"]
                break

        packages.append(SBOMPackage(
            name=name,
            version=version,
            ecosystem=ecosystem,
            purl=purl
        ))

    return packages


def parse_sbom(filepath: str) -> List[SBOMPackage]:
    """Parse an SBOM file (auto-detects format).

    Args:
        filepath: Path to SBOM JSON file

    Returns:
        List of SBOMPackage objects

    Raises:
        ValueError: If format cannot be detected or is unsupported
    """
    with open(filepath, 'r') as f:
        data = json.load(f)

    # Detect format
    if "bomFormat" in data and data.get("bomFormat") == "CycloneDX":
        return parse_cyclonedx(data)
    elif "spdxVersion" in data:
        return parse_spdx(data)
    elif "components" in data:
        # Assume CycloneDX without bomFormat field
        return parse_cyclonedx(data)
    elif "packages" in data:
        # Assume SPDX without spdxVersion field
        return parse_spdx(data)
    else:
        raise ValueError("Unknown SBOM format. Supported: CycloneDX, SPDX (JSON)")
