#!/usr/bin/env python3
"""
Test script to verify the UEIL Data Store setup
"""

import requests
import json
import time
import sys
from pathlib import Path

# Configuration
API_BASE = "http://localhost:8001"
FRONTEND_BASE = "http://localhost:8501"


def test_api_health():
    """Test if the API is running"""
    try:
        response = requests.get(f"{API_BASE}/status", timeout=5)
        if response.status_code == 200:
            print("✅ API is running")
            return True
        else:
            print(f"❌ API returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ API connection failed: {e}")
        return False


def test_frontend_health():
    """Test if the frontend is running"""
    try:
        response = requests.get(f"{FRONTEND_BASE}/_stcore/health", timeout=5)
        if response.status_code == 200:
            print("✅ Frontend is running")
            return True
        else:
            print(f"❌ Frontend returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Frontend connection failed: {e}")
        return False


def test_search_endpoints():
    """Test search endpoints"""
    try:
        # Test folder search
        response = requests.get(f"{API_BASE}/search?limit=5")
        if response.status_code == 200:
            print("✅ Folder search endpoint working")
        else:
            print(f"❌ Folder search failed: {response.status_code}")
            return False

        # Test file search
        response = requests.get(f"{API_BASE}/search_files?limit=5")
        if response.status_code == 200:
            print("✅ File search endpoint working")
            return True
        else:
            print(f"❌ File search failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Search endpoints failed: {e}")
        return False


def create_test_metadata():
    """Create a test metadata file"""
    metadata = {
        "research_project_id": "Test_Project",
        "author": "Test_Researcher",
        "experiment_type": "Test_Experiment",
        "date_conducted": "2025-01-19",
        "custom_tags": "test, validation, setup",
        "notes": "Test metadata for setup validation",
    }

    with open("test_metadata.yaml", "w") as f:
        import yaml

        yaml.dump(metadata, f, default_flow_style=False)

    print("✅ Test metadata file created")


def test_file_upload():
    """Test file upload functionality"""
    try:
        # Create a test file
        with open("test_file.txt", "w") as f:
            f.write("This is a test file for validation")

        # Create test metadata
        create_test_metadata()

        # Test upload
        with (
            open("test_file.txt", "rb") as data_file,
            open("test_metadata.yaml", "rb") as metadata_file,
        ):
            files = {
                "data_file": ("test_file.txt", data_file, "text/plain"),
                "metadata_file": (
                    "test_metadata.yaml",
                    metadata_file,
                    "application/x-yaml",
                ),
            }

            response = requests.post(f"{API_BASE}/uploadfile/", files=files)

            if response.status_code == 200:
                print("✅ File upload working")
                result = response.json()
                print(f"   Uploaded file ID: {result.get('file_id', 'N/A')}")
                return True
            else:
                print(f"❌ File upload failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
    except Exception as e:
        print(f"❌ File upload test failed: {e}")
        return False
    finally:
        # Cleanup test files
        for file in ["test_file.txt", "test_metadata.yaml"]:
            if Path(file).exists():
                Path(file).unlink()


def main():
    """Run all tests"""
    print("🧪 Testing UEIL Data Store Setup")
    print("=" * 40)

    tests = [
        ("API Health", test_api_health),
        ("Frontend Health", test_frontend_health),
        ("Search Endpoints", test_search_endpoints),
        ("File Upload", test_file_upload),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n🔍 Testing {test_name}...")
        result = test_func()
        results.append((test_name, result))

    print("\n" + "=" * 40)
    print("📊 Test Results:")

    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1

    print(f"\n🎯 Summary: {passed}/{len(results)} tests passed")

    if passed == len(results):
        print("🎉 All tests passed! Your setup is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
