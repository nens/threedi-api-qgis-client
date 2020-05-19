#!/bin/bash
set -e
set -u

VERSION=$(grep "^version" ./threedi_api_qgis_client/metadata.txt | cut -d= -f2)

# ARTIFACTS_KEY should be set as env variable in the travis UI.
# TRAVIS_BRANCH is set automatically by travis
ARTIFACT=threedi_api_qgis_client_${VERSION}.zip
PROJECT=threedi_api_qgis_client

# Rename generated threedi_api_qgis_client.zip to include version number.
cp threedi_api_qgis_client.zip ${ARTIFACT}

curl -X POST \
     --retry 3 \
     -H "Content-Type: multipart/form-data" \
     -F key=${ARTIFACTS_KEY} \
     -F artifact=@${ARTIFACT} \
     -F branch=${TRAVIS_BRANCH} \
     https://artifacts.lizard.net/upload/${PROJECT}/
