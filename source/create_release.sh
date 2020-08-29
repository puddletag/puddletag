#!/bin/bash
BUILD_DIR=$(pwd)/releases/"release_"$(date +"%Y_%m_%d_%H%M%S")

echo Created dir $BUILD_DIR
mkdir -p $BUILD_DIR

echo "Creating source release"
python2 setup.py --quiet sdist --owner=root --group=root --dist-dir=$BUILD_DIR 

# echo "Making documentation"
cd ../puddletag-docs

python3 offlinezip.py $BUILD_DIR

cd ../puddletag-docs
python3 update_checksums.py checksums.txt $BUILD_DIR
make html
mv _build/html $BUILD_DIR/website

echo "Release built"

