#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring, line-too-long

import os
import json
import difflib
import subprocess
import shutil

# Directory where JSON files are located
DATA_DIR = "data"

# Change working directory to DATA_DIR
os.chdir(DATA_DIR)

# List of JSON files with deltas from the last commit
delta_files = []
unchanged_files = []

# Get the list of files mentioned by git status
git_executable = shutil.which("git")
if git_executable is None:
    print("Git executable not found. Please make sure Git is installed and in the system PATH.")
    exit(1)

git_status_files = [
    line.split()[-1] for line in subprocess.run([git_executable, "status", "-s"], capture_output=True, text=True).stdout.splitlines()
]

# Function to sort arrays within JSON objects
def sort_arrays(obj):
    if isinstance(obj, dict):
        return {k: sort_arrays(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return sorted(obj)
    return obj

# Loop over JSON files in the DATA_DIR
for json_file in os.listdir('.'):
    if json_file.endswith(".json"):
        # Check if the JSON file differs from the last commit (HEAD)
        if json_file not in git_status_files:
            continue

        # Extract JSON file in the current commit
        current_json = subprocess.run([git_executable, "show", f"HEAD:{json_file}"], capture_output=True, text=True).stdout

        # Extract JSON file in the working copy
        with open(json_file, "r") as file:
            working_copy_json = file.read()

        # Load JSON data
        current_data = json.loads(current_json)
        working_copy_data = json.loads(working_copy_json)

        # Ignore the "SOA" key in the comparison
        for key in current_data:
            current_data[key].pop("SOA", None)
        for key in working_copy_data:
            working_copy_data.pop("SOA", None)

        # Sort arrays within JSON objects
        current_data_sorted = sort_arrays(current_data)
        working_copy_data_sorted = sort_arrays(working_copy_data)

        # Compare JSON files
        if current_data_sorted != working_copy_data_sorted:
            delta_files.append(json_file)
            print(f"Delta found in {json_file}:")
            diff = difflib.unified_diff(
                json.dumps(current_data_sorted, indent=2).splitlines(),
                json.dumps(working_copy_data_sorted, indent=2).splitlines(),
            )
            print("\n".join(diff))
            print("-------------------------------")
        else:
            unchanged_files.append(json_file)

print()

# Option to reset files to their previous state
if unchanged_files:
    print("Unchanged: ")
    print(unchanged_files)
    reset_option = input(
        "Do you want to reset the unchanged files to their previous state? (y/n): "
    )
    if reset_option.lower() == "y":
        for file in unchanged_files:
            subprocess.run([git_executable, "checkout", "HEAD", file])
        print("Unchanged files have been reset to their previous state.")
    else:
        print("No files were reset.")
else:
    print("No unchanged files found.")
