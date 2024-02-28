#!/usr/bin/python3
# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring, line-too-long

import os
import json
import difflib

# Directory where JSON files are located
DATA_DIR = "data"

# List of JSON files with deltas from the last commit
delta_files = []
unchanged_files = []

# Get the list of files mentioned by git status
git_status_files = [
    line.split()[-1] for line in os.popen("git status -s").read().splitlines()
]

# Function to sort arrays within JSON objects
def sort_arrays(obj):
    if isinstance(obj, dict):
        return {k: sort_arrays(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return sorted(obj)
    return obj

# Loop over JSON files in the DATA_DIR
for json_file in os.listdir(DATA_DIR):
    if json_file.endswith(".json"):
        # Check if the JSON file differs from the last commit (HEAD)
        if os.path.join(DATA_DIR, json_file) not in git_status_files:
            continue

        # Extract JSON file in the current commit
        current_json = os.popen(f"git show HEAD:{os.path.join(DATA_DIR, json_file)}").read()

        # Extract JSON file in the working copy
        with open(os.path.join(DATA_DIR, json_file), "r") as file:
            working_copy_json = file.read()

        # Load JSON data
        current_data = json.loads(current_json)
        working_copy_data = json.loads(working_copy_json)

        # Ignore the "SOA" key in the comparison
        current_data.pop("SOA", None)
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
            os.system(f"git checkout HEAD {os.path.join(DATA_DIR, file)}")
        print("Unchanged files have been reset to their previous state.")
    else:
        print("No files were reset.")
else:
    print("No unchanged files found.")
