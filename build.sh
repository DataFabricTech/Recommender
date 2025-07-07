#!/bin/bash
version=v1.0.0
headHash=$(git rev-parse --short=7 HEAD)
today=$(date +%Y%m%d)
imageName="repo.iris.tools/datafabric/recommender"
tag=${version}-RC${today}-${headHash}
SENTRY_RELEASE="prod"

function check() {
        echo "==============================================="
        echo "## Docker Check"
        echo "==============================================="

        if [ ! -d $docker ]; then
                echo "==============================================="
                echo 'docker command not found'
                echo "==============================================="
                exit 1
        else
                echo "==============================================="
                echo 'docker check OK'
                echo "==============================================="
        fi
}

function build() {
        echo "==============================================="
        echo "## Docker Build Start"
        echo "==============================================="

        echo $imageName
        echo $tag

        docker build --platform linux/amd64 -f ./Dockerfile -t $imageName:$tag .

        if [ $? != 0 ]; then
                echo "[ERROR] docker build failed."
                exit 1
        fi
}

check
build

echo "==============================================="
echo "## Docker Build End - $imageName:$tag"
echo "==============================================="

