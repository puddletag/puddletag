#! /bin/bash

function create_bundle_structure () {
      mkdir -p ${bundleMacOSFolder}
      mkdir -p ${bundleResourcesFolder}
}

function provide_app_startup_script () {
      cp ${appStartupScript} ${bundleMacOSFolder}/${1}
}

function provide_app_icon () {
      $(which sips) -s format icns ${2} --out ${bundleResourcesFolder}/${1}.icns > /dev/null
}

function create_Info.plist () {
echo -e "<?xml version="1.0" encoding="UTF-8"?>
      <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
      <plist version="1.0">
      <dict>
        <key>CFBundleDevelopmentRegion</key>
        <string>English</string>
        <key>CFBundleExecutable</key>
        <string>${2}</string>" > ${1}.app/Contents/Info.plist

if [[ ${3} != "empty" ]]; then
echo -e "        <key>CFBundleIconFile</key>
        <string>${3}</string>" >> ${1}.app/Contents/Info.plist
fi

echo -e "        <key>CFBundleIdentifier</key>
        <string>com.github.keithgg.puddletag</string>
        <key>CFBundleInfoDictionaryVersion</key>
        <string>6.0</string>
        <key>CFBundlePackageType</key>
        <string>APPL</string>
        <key>CFBundleVersion</key>
        <string>1.0</string>
        <key>CFBundleSignature</key>
        <string>PUDDLE</string>
      </dict>
      </plist>" >> ${1}.app/Contents/Info.plist
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

if [[ ! $(which sip) ]]; then
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
create_Info.plist ${appName} ${appStartupScript} ${appIcon}

# EoF
