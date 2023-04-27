#!/bin/bash
set -e
cd "${0%/*}/.."

TAG="${VERSION:-latest}"
IMAGE="${IMAGE:-neat-docs}"
PUBLISH="${PUBLISH:-false}"

echo "Building image $IMAGE:$TAG"

poetry run mkdocs build

set +e
if $PUBLISH -eq "true"; then
  pack build "$IMAGE:$TAG" --buildpack paketo-buildpacks/nginx \
                           --builder paketobuildpacks/builder:base \
                           --env BP_WEB_SERVER_ROOT=site \
                           --env BP_WEB_SERVER=nginx \
                           --publish
else
  pack build "$IMAGE:$TAG" --buildpack paketo-buildpacks/nginx \
                           --builder paketobuildpacks/builder:base \
                           --env BP_WEB_SERVER_ROOT=site \
                           --env BP_WEB_SERVER=nginx
fi
EXIT=$?
set -e

rm -rf site

exit $EXIT
