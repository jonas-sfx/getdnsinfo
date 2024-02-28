#!/bin/bash

## filename     recheckall.sh
## description: run the python-script getdnsinfo.py
##              for each basename of the json-files in ./data
## author:      jonas@sfxonline.de
## =======================================================================

for filename in data/*.json; do
    echo
    echo "==> "$(basename "$filename" .json)
    ./getdnsinfo.py -d $(basename "$filename" .json)
    echo
done
./reset-nonchanges.py
