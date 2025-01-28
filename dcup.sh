#!/bin/bash
#
# Convenience script to run docker compose with multiple compose files
#
# Usage: ./dcup.sh [compose_file1] [compose_file2] ...
#
# Files are assumed to have format docker-compose.[LABEL].yml and live in the docker/ directory
# e.g. to run with docker/docker-compose.dev.yml:
# ./dcup.sh dev
#
# To run with multiple files:
# ./dcup.sh dev gpu
#
compose_files="-f docker-compose.yml"
for arg in "$@"; do
    compose_files="$compose_files -f docker/docker-compose.$arg.yml"
done
echo "Running docker compose $compose_files"
docker compose $compose_files up
