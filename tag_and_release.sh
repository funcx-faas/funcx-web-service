#!/bin/bash
# Script to release a new version of the web service
# It does this by creating a branch named after the version, updating
# version.py, committing those changes to the branch
#
# Usage:
# tag_and_release.sh version
# The version should be the semantic version for this new release

if [ $# -ne 1 ]; then
    echo "Usage tag_and_release version"
    exit 1
fi

VERSION=$1

SEMVER_REGEX="^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)(\\-[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?(\\+[0-9A-Za-z-]+(\\.[0-9A-Za-z-]+)*)?$"

if [[ ! $VERSION =~ $SEMVER_REGEX ]]; then
  echo "Version should be a nice Semantic Version String (https://semver.org)"
  exit 1
fi

verify_version() {
  FUNCX_VERSION=$(python3 -c "import funcx_web_service.version; print(funcx_web_service.version.VERSION)")

  if [[ $FUNCX_VERSION == "$VERSION" ]]
  then
      echo "Version requested matches package version: $VERSION"
  else
      echo "Updating version.py to match release"
      sed "s/^VERSION *= *'.*'/VERSION = '$VERSION'/" funcx_web_service/version.py > funcx_web_service/version.py.bak
      mv  funcx_web_service/version.py.bak funcx_web_service/version.py
      git status
  fi
}


create_release_branch () {
    echo "Creating branch"
    git checkout -b "v$VERSION"
    git add funcx_web_service/version.py
    git commit -m "Update to version $VERSION"

    echo "Pushing branch"
    git push origin "v$VERSION"
}


verify_version
create_release_branch

