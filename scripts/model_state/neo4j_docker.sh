#!/bin/bash
set -e

NEO4J_DIR=$HOME/neo4j
NEO4J_CONTAINER_NAME=neo4j-osm
NEO4J_IMAGE_NAME=neo4j_img
USAGE_TEXT=$'Usage: ./neo4j_docker.sh ACTION CSV_FILE [NEO4J_DIR] [NEO4J_CONTAINER_NAME]
            ACTION = one of start, stop, clean
            CSV_FILE is only needed for ACTION=start'

setNeo4jPaths() {
  if [ -z "$1" ]; then
    echo "Using default path for neo4j directory: $NEO4J_DIR"
  elif [ "$1" = "${1#/}" ]; then
    echo "Relative paths for the mounted neo4j directory cannot be used, please specify an absolute path. Variables are OK."
    exit 1
  else
    echo "Using $1 as the neo4j directory"
    NEO4J_DIR=${1%/}
  fi

  if [ -z "$2" ]; then
    echo "Using default neo4j docker container name: $NEO4J_CONTAINER_NAME"
  else
    echo "Using $2 as the neo4j docker container name"
    NEO4J_CONTAINER_NAME=$2
  fi
}

startNeo4j() {
  if [ -z "$1" ]; then
    echo "Please specify a CSV file for importing"
    exit 1
  fi

  # make mounted directories
  if [ -d $NEO4J_DIR ]; then
    echo "Using existing neo4j directory."
  else
    echo "Making neo4j data directory at $NEO4J_DIR"
    mkdir $NEO4J_DIR $NEO4J_DIR/data $NEO4J_DIR/import $NEO4J_DIR/plugins
  fi

  cp $1 $NEO4J_DIR/import/

  python neo4j_config_set.py --url neo4j://localhost:7687 --user neo4j --password password

  # build the image from the dockerfile
  echo "Building docker image"
  docker build . -t $NEO4J_IMAGE_NAME -q

  if docker ps -a --format '{{.Names}}' | grep -Eq $NEO4J_CONTAINER_NAME; then
    echo "Container exists, restarting..."
    docker restart $NEO4J_CONTAINER_NAME 
    sleep 15 # wait for neo4j to initialize
  else
    echo "Running container..."
    docker run \
      --restart always \
      -d \
      -p 7474:7474 -p 7687:7687 \
      -v $NEO4J_DIR/data:/data -v $NEO4J_DIR/plugins:/plugins -v $NEO4J_DIR/import:/import \
      --name $NEO4J_CONTAINER_NAME \
      $NEO4J_IMAGE_NAME
    sleep 20 # wait for neo4j to initialize
  fi

  if python import_csv.py --file $1; then
    echo "Imported CSV."
  else
    echo ""
    echo "CSV import failed, please manually run 'python import_csv.py --file <local_file>'"
  fi

  echo "Open http://localhost:7474 in browser for the neo4j console. User: neo4j, Password: password."
}

stopNeo4j() {
  echo "Stopping container..."
  docker stop $NEO4J_CONTAINER_NAME
}

cleanNeo4j() {
  stopNeo4j
  echo "Removing container..."
  docker rm $NEO4J_CONTAINER_NAME
  echo "Removing image..."
  docker rmi $NEO4J_IMAGE_NAME
  echo "Deleting $NEO4J_DIR"
  sudo rm -rf $NEO4J_DIR
}

if [ -z "$1" ]; then
  echo "Please specify whether to start, stop or clean the neo4j instance."
  echo "$USAGE_TEXT"
  exit 1
fi

case "$1" in
start)
  setNeo4jPaths "${@:3}"
  startNeo4j "${@:2:1}"
  ;;
stop)
  setNeo4jPaths "${@:2}"
  stopNeo4j
  ;;
clean)
  setNeo4jPaths "${@:2}"
  cleanNeo4j
  ;;
*)
    echo $USAGE_TEXT
    ;;
esac