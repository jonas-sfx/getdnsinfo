# GetDNS-Info

A Python tool to retrieve DNS information and store it as JSON for version control systems.

[![CodeFactor](https://www.codefactor.io/repository/github/jonas-sfx/getdnsinfo/badge)](https://www.codefactor.io/repository/github/jonas-sfx/getdnsinfo)

## Features

Retrieve DNS information using Python and store it as JSON.

## Submodule

User the data subdirectory as a submodule.
Without this configuration, [`reset-nonchanges.py`](reset-nonchanges.py) might not function properly, potentially leading to false-positive anounced changes. Actually this script should recoginze and undo them.
