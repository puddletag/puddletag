if [ -z "$1" ]
  then
    echo "Please enter your SourceForge username as the first argument.";
    exit;
fi

USER=$1

BUILD_DIR=$(pwd)/releases/"release_"$(date +"%Y_%m_%d_%H%M%S")

echo Created dir $BUILD_DIR
mkdir -p $BUILD_DIR

echo "Making deb"
fakeroot python2 makerelease.py $BUILD_DIR

echo "Creating source release"
python2 setup.py --quiet sdist --owner=root --group=root --dist-dir=$BUILD_DIR 

# echo "Making documentation"
cd ../puddletag-docs

python2 offlinezip.py $BUILD_DIR

cd ../puddletag-docs
make html
mv _build/html $BUILD_DIR/website

echo "Uploading files to sourceforge"
cd $BUILD_DIR
# rsync -acP -e ssh website $USER@frs.sourceforge.net:/home/project-web/puddletag/htdocs
# rsync -acP -e ssh *.tar.gz *.deb $USER@frs.sourceforge.net:/home/frs/project/p/pu/puddletag/ 
# rsync -acP -e ssh *.bz2 $USER@frs.sourceforge.net:/home/frs/project/p/pu/puddletag/docs

echo "Release uploaded"
