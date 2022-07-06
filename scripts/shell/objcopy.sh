#!/bin/bash

# set -x

COPY=${COPY:-objcopy}

PATTERN='.*\.o'
for VAR in "$@"; do
	if [[ ${VAR} =~ ${PATTERN} ]]; then
		if [[ -z ${SOURCE} ]]; then
			SOURCE=`echo ${VAR} | sed -e 's/\.o/\.bc/'`
		else
			TARGET=`echo ${VAR} | sed -e 's/\.o/\.bc/'`
		fi
	fi
done

if [[ -e ${SOURCE} && -n ${TARGET} ]]; then
	cp ${SOURCE} ${TARGET} && llvm-dis ${TARGET} && ${COPY} "$@"
else
	${COPY} "$@"
fi
