#!/bin/bash
set -e
set -u

VERSION=$(grep "^version" ./threedi_models_and_simulations/metadata.txt | cut -d= -f2)

# ARTIFACTS_KEY should be set as env variable in the travis UI.
# TRAVIS_BRANCH is set automatically by travis
ARTIFACT=threedi_models_and_simulations.${VERSION}.zip
PROJECT=threedi-api-qgis-client

curl -X POST \
     --retry 3 \
     -H "Content-Type: multipart/form-data" \
     -F key=${ARTIFACTS_KEY} \
     -F artifact=@${ARTIFACT} \
     https://artifacts.lizard.net/upload/${PROJECT}/
