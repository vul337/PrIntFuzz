#!/bin/bash

CLANG=${CLANG:-clang}

ARGS=''
PATTERN='-D.*="((?!D).)*"'
for VAR in "$@"; do
	VAR=`echo "${VAR}" | perl -pe 's/="(((?!-D).)*)"/=\x27"\1"\x27/g'`
	VAR=`echo "${VAR}" | sed -e 's/-D\(.* fmt\)/-D\x27\1\x27/g'`
	ARGS="${ARGS} ${VAR}"
done

PATTERN='-o .*\.o .*\.c'
if [[ "$@" =~ ${PATTERN}  ]]; then
	PREFIX=`echo "${ARGS}" | sed -e 's/\(.*-o\) .*/\1/'`
	SOURCE_FILE=`echo "${ARGS}" | sed -e 's/.*\.o \(.*\)/\1/'`
	TARGET_NAME=`echo "${ARGS}" | sed -e 's/.* \(.*\.o\) .*/\1/'`
	if [[ ${TARGET_NAME} == *"tmp_"* ]]; then
		TARGET_NAME=`echo "${TARGET_NAME}" | sed -e 's/\(.*\)\.tmp_\(.*\)/\1\2/'`
	fi
	BC_NAME=`echo ${TARGET_NAME} | sed -e 's/\.o/\.bc/'`
	PREPROCESS_NAME=`echo ${TARGET_NAME} | sed -e 's/\.o/\.i/'`
	LL_NAME=`echo ${TARGET_NAME} | sed -e 's/\.o/\.ll/'`
fi

if [[ ${BUILD_TYPE} == 'ALLMOD' ]]; then
	EXTRA_FLAG='-O0'
else
	EXTRA_FLAG=''
fi

if [ ! -z "${PREFIX}" ]; then
	CMD1="${CLANG} -emit-llvm ${PREFIX} ${BC_NAME} ${EXTRA_FLAG} ${SOURCE_FILE}"
	CMD2="${CLANG} -S -emit-llvm ${PREFIX} ${LL_NAME} ${EXTRA_FLAG} ${SOURCE_FILE}"
	CMD3="${CLANG} -E ${PREFIX} ${PREPROCESS_NAME} ${EXTRA_FLAG} ${SOURCE_FILE}"
fi

# set -x

PATTERN='".* [^=]*"'
if [[ "$@" =~ $PATTERN   ]]; then
	eval ${CMD1} && eval ${CMD2} && eval "${CLANG} ${ARGS}"
else
	eval ${CMD1} && eval ${CMD2} && ${CLANG} $@
fi
