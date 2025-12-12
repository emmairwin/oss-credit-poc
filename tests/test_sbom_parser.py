"""Tests for SBOM parser."""

import json
import tempfile
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sbom_parser import parse_sbom, SBOMPackage


class TestParseSBOMCycloneDX:
    """Tests for CycloneDX SBOM parsing via lib4sbom."""

    def test_parse_cyclonedx_json(self):
        data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "version": 1,
            "components": [
                {
                    "type": "library",
                    "name": "requests",
                    "version": "2.31.0",
                    "purl": "pkg:pypi/requests@2.31.0"
                },
                {
                    "type": "library",
                    "name": "lodash",
                    "version": "4.17.21",
                    "purl": "pkg:npm/lodash@4.17.21"
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cdx.json', delete=False) as f:
            json.dump(data, f)
            f.flush()
            try:
                packages = parse_sbom(f.name)
            finally:
                os.unlink(f.name)

        assert len(packages) == 2
        pkg_names = {p.name for p in packages}
        assert "requests" in pkg_names
        assert "lodash" in pkg_names

        requests_pkg = next(p for p in packages if p.name == "requests")
        assert requests_pkg.purl == "pkg:pypi/requests@2.31.0"
        assert requests_pkg.version == "2.31.0"

    def test_parse_scoped_npm_package(self):
        data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "version": 1,
            "components": [
                {
                    "type": "library",
                    "name": "@babel/core",
                    "version": "7.22.0",
                    "purl": "pkg:npm/%40babel/core@7.22.0"
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cdx.json', delete=False) as f:
            json.dump(data, f)
            f.flush()
            try:
                packages = parse_sbom(f.name)
            finally:
                os.unlink(f.name)

        assert len(packages) == 1
        assert packages[0].name == "@babel/core"
        assert packages[0].purl == "pkg:npm/%40babel/core@7.22.0"


class TestParseSBOMSPDX:
    """Tests for SPDX SBOM parsing via lib4sbom."""

    def test_parse_spdx_json(self):
        data = {
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": "test-sbom",
            "documentNamespace": "https://example.com/test",
            "creationInfo": {
                "created": "2024-01-01T00:00:00Z",
                "creators": ["Tool: test"]
            },
            "packages": [
                {
                    "SPDXID": "SPDXRef-Package-numpy",
                    "name": "numpy",
                    "versionInfo": "1.24.0",
                    "downloadLocation": "NOASSERTION",
                    "filesAnalyzed": False,
                    "externalRefs": [
                        {
                            "referenceCategory": "PACKAGE-MANAGER",
                            "referenceType": "purl",
                            "referenceLocator": "pkg:pypi/numpy@1.24.0"
                        }
                    ]
                }
            ]
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.spdx.json', delete=False) as f:
            json.dump(data, f)
            f.flush()
            try:
                packages = parse_sbom(f.name)
            finally:
                os.unlink(f.name)

        assert len(packages) == 1
        assert packages[0].name == "numpy"
        assert packages[0].version == "1.24.0"
        assert packages[0].purl == "pkg:pypi/numpy@1.24.0"


class TestParseSBOMEmpty:
    """Tests for empty SBOM handling."""

    def test_empty_cyclonedx(self):
        data = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.4",
            "version": 1,
            "components": []
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cdx.json', delete=False) as f:
            json.dump(data, f)
            f.flush()
            try:
                packages = parse_sbom(f.name)
            finally:
                os.unlink(f.name)

        assert packages == []
