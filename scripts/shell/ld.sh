#!/bin/bash

LINKER=${LINKER:-ld}

# set -x

${LINKER} "$@"
