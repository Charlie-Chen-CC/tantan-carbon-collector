#!/usr/bin/env python3
"""测试 Section 7 提取功能"""
import sys
import os

# Current dir is tantan/, so tantan package is at .
workspace_root = os.getcwd()  # This is tantan/
sys.path.insert(0, os.path.dirname(workspace_root))  # parent dir

from tantan.backend.agents.file_extractor import FileExtractAgent

def main():
    # Find the 三废处理 test file
    section7_dir = os.path.join(workspace_root, "test_doc", "extractable_by_section", "section7")

    test_file = None
    for f in os.listdir(section7_dir):
        if "三废处理" in f:
            test_file = os.path.join(section7_dir, f)
            break

    if not test_file:
        print("Error: 三废处理测试数据.xlsx not found")
        return 1

    print(f"Using test file: {test_file}")

    with open(test_file, 'rb') as f:
        content = f.read()
    print(f"File size: {len(content)} bytes")

    agent = FileExtractAgent(section=7)
    result = agent.process(content, os.path.basename(test_file))

    print(f"\nExtraction result:")
    print(f"  Status: {result['status']}")
    print(f"  Error: {result.get('error', 'none')}")

    if result.get('data'):
        print(f"\nExtracted data ({len(result['data'])} fields):")
        for key, value in result['data'].items():
            print(f"  {key}: {value}")
        return 0
    else:
        print("\nNo data extracted!")
        return 1

if __name__ == "__main__":
    sys.exit(main())