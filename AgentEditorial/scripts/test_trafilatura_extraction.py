#!/usr/bin/env python3
"""Test Trafilatura extraction on innosys.fr to verify boilerplate removal."""

import sys
from pathlib import Path

import requests

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directly from extractor module to avoid dependency issues
import importlib.util
spec = importlib.util.spec_from_file_location(
    "extractor",
    Path(__file__).parent.parent / "python_scripts" / "agents" / "scrapping" / "extractor.py"
)
extractor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extractor_module)
AdaptiveExtractor = extractor_module.AdaptiveExtractor


def test_extraction(url: str = "https://innosys.fr"):
    """Test extraction with and without Trafilatura."""
    print(f"\n{'='*80}")
    print(f"Testing Trafilatura Extraction")
    print(f"{'='*80}")
    print(f"URL: {url}\n")

    # Fetch HTML
    print("📡 Fetching HTML...")
    response = requests.get(url, timeout=30.0)
    html = response.text
    print(f"✅ HTML fetched ({len(html):,} bytes)\n")

    # Test WITH Trafilatura
    print("🔹 Test 1: WITH Trafilatura (Boilerplate Removal)")
    print("-" * 80)
    extractor_with = AdaptiveExtractor(use_trafilatura=True)

    # Since extract_article_adaptive is async, we need to use asyncio
    import asyncio
    article_with = asyncio.run(extractor_with.extract_article_adaptive(
        html=html,
        url=url,
        profile={},  # No profile
    ))

    print(f"Extraction method: {article_with.get('extraction_method', 'N/A')}")
    print(f"Title: {article_with.get('title', 'N/A')[:80]}")
    print(f"Word count: {article_with.get('word_count', 0)}")
    print(f"\nData Quality:")
    quality_with = article_with.get("data_quality", {})
    for key, value in quality_with.items():
        print(f"  - {key}: {value}")

    print(f"\nContent preview (first 500 chars):")
    print(f"  {article_with.get('content', '')[:500]}")

    # Test WITHOUT Trafilatura (CSS selectors only)
    print(f"\n{'='*80}")
    print("🔹 Test 2: WITHOUT Trafilatura (CSS Selectors Only)")
    print("-" * 80)
    extractor_without = AdaptiveExtractor(use_trafilatura=False)
    article_without = asyncio.run(extractor_without.extract_article_adaptive(
        html=html,
        url=url,
        profile={},
    ))

    print(f"Extraction method: {article_without.get('extraction_method', 'N/A')}")
    print(f"Title: {article_without.get('title', 'N/A')[:80]}")
    print(f"Word count: {article_without.get('word_count', 0)}")
    print(f"\nData Quality:")
    quality_without = article_without.get("data_quality", {})
    for key, value in quality_without.items():
        print(f"  - {key}: {value}")

    print(f"\nContent preview (first 500 chars):")
    print(f"  {article_without.get('content', '')[:500]}")

    # Comparison
    print(f"\n{'='*80}")
    print("📊 COMPARISON")
    print(f"{'='*80}")

    word_count_diff = article_with.get('word_count', 0) - article_without.get('word_count', 0)
    density_with = quality_with.get('content_density', 0)
    density_without = quality_without.get('content_density', 0)
    density_improvement = (density_with - density_without) / density_without * 100 if density_without > 0 else 0

    print(f"\nWord Count:")
    print(f"  - WITH Trafilatura: {article_with.get('word_count', 0):,} words")
    print(f"  - WITHOUT Trafilatura: {article_without.get('word_count', 0):,} words")
    print(f"  - Difference: {word_count_diff:+,} words ({word_count_diff / article_without.get('word_count', 1) * 100:+.1f}%)")

    print(f"\nContent Density:")
    print(f"  - WITH Trafilatura: {density_with:.3f}")
    print(f"  - WITHOUT Trafilatura: {density_without:.3f}")
    print(f"  - Improvement: {density_improvement:+.1f}%")

    print(f"\nBoilerplate Detection:")
    print(f"  - WITH Trafilatura: {quality_with.get('boilerplate_detected', False)}")
    print(f"  - WITHOUT Trafilatura: {quality_without.get('boilerplate_detected', False)}")

    # Success criteria
    print(f"\n{'='*80}")
    print("✅ SUCCESS CRITERIA")
    print(f"{'='*80}")

    success = True
    if article_with.get('extraction_method') != 'trafilatura':
        print(f"❌ FAIL: Trafilatura extraction not used")
        success = False
    else:
        print(f"✅ PASS: Trafilatura extraction successful")

    if density_with <= density_without:
        print(f"⚠️  WARNING: Content density not improved (may need investigation)")
    else:
        print(f"✅ PASS: Content density improved by {density_improvement:.1f}%")

    if quality_with.get('boilerplate_detected'):
        print(f"⚠️  WARNING: Boilerplate still detected in Trafilatura extraction")
    else:
        print(f"✅ PASS: No boilerplate detected in clean extraction")

    return success


if __name__ == "__main__":
    success = test_extraction()
    sys.exit(0 if success else 1)
