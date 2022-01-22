#! /bin/bash

function create_bundle_structure () {
      mkdir -p ${bundleMacOSFolder}
      mkdir -p ${bundleResourcesFolder}
}

function provide_app_startup_script () {
      cp ${1} ${bundleMacOSFolder}/${1##*/}
      chmod 755 ${bundleMacOSFolder}/${1##*/}
}

function provide_app_icon () {
      $(which sips) -s format icns ${2} --out ${bundleResourcesFolder}/${1}.icns >> /dev/null
}

function create_Info_plist () {
echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" > ${1}.app/Contents/Info.plist
echo "<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">" >> ${1}.app/Contents/Info.plist
echo "<plist version=\"1.0\">" >> ${1}.app/Contents/Info.plist
echo "<dict>" >> ${1}.app/Contents/Info.plist
echo "    <key>CFBundleName</key>" >> ${1}.app/Contents/Info.plist
echo "    <string>${1}</string>" >> ${1}.app/Contents/Info.plist
echo "    <key>CFBundleExecutable</key>" >> ${1}.app/Contents/Info.plist
echo "    <string>${2##*/}</string>" >> ${1}.app/Contents/Info.plist

if [[ ${3} != "empty" ]]; then
    echo "    <key>CFBundleIconFile</key>" >> ${1}.app/Contents/Info.plist
    echo "    <string>${1}.icns</string>" >> ${1}.app/Contents/Info.plist
fi

echo "    <key>CFBundleIdentifier</key>" >> ${1}.app/Contents/Info.plist
echo "    <string>com.github.keithgg.puddletag</string>" >> ${1}.app/Contents/Info.plist
echo "    <key>CFBundleInfoDictionaryVersion</key>" >> ${1}.app/Contents/Info.plist
echo "    <string>6.0</string>" >> ${1}.app/Contents/Info.plist
echo "    <key>CFBundlePackageType</key>" >> ${1}.app/Contents/Info.plist
echo "    <string>APPL</string>" >> ${1}.app/Contents/Info.plist
echo "    <key>CFBundleVersion</key>" >> ${1}.app/Contents/Info.plist
echo "    <string>1.0</string>" >> ${1}.app/Contents/Info.plist
echo "    <key>CFBundleSignature</key>" >> ${1}.app/Contents/Info.plist
echo "    <string>PUDDLE</string>" >> ${1}.app/Contents/Info.plist
echo "</dict>" >> ${1}.app/Contents/Info.plist
echo "</plist>" >> ${1}.app/Contents/Info.plist
}

###################################
# Main routine
###################################
appIcon="empty"

while [[ $# > 1 ]]; do
      key="${1}"

      case $key in
         -n|--name)
           appName="${2}"
           shift # past argument
           ;;

         -i|--icon)
           appIcon="${2}"
           shift # past argument
           ;;

         -s|--script)
           appStartupScript="${2}"
           shift # past argument
           ;;

         *)
           echo "Unknown argument \"${key}\"."
           show_help_message
           shift # past argument
           ;;
      esac
      shift # past argument or value
done

if [[ ! $(which sips) ]]; then
      appIcon="empty"
fi

# internal vars
bundleMacOSFolder=${appName}.app/Contents/MacOS
bundleResourcesFolder=${appName}.app/Contents/Resources

# create the bundle
create_bundle_structure 
provide_app_startup_script ${appStartupScript}
if [[ ${appIcon} != "empty" ]]; then
       provide_app_icon ${appName} ${appIcon}
fi
create_Info_plist ${appName} ${appStartupScript} ${appIcon}

# EoF
