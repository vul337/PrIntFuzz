#!/bin/bash

ARCHIVE=${ARCHIVE:-ar}

check_bc() {
	SOURCE_BCS=''
	SOURCE_OBJECTS=''
	for SOURCE_FILE in ${SOURCE_FILES}; do
		if [[ ${SOURCE_FILE} == *"tmp_"* ]]; then
			SOURCE_FILE=`echo "${SOURCE_FILE}" | sed -e 's/\(.*\)\.tmp_\(.*\)/\1\2/'`
		fi
		SOURCE_BC=`echo ${SOURCE_FILE} | sed -e 's/\.o/\.bc/g'`
		if [[ -e ${SOURCE_BC} ]]; then
			SOURCE_BCS="${SOURCE_BCS} ${SOURCE_BC}"
		else
			SOURCE_OBJECTS="${SOURCE_OBJECTS} ${SOURCE_FILE}"
		fi
	done
}

write_dep() {
	DEP_FILE=${TARGET_BC}.dep
	CONTENT="${TARGET_BC}:${SOURCE_BCS} ${SOURCE_OBJECTS}"
	echo "${CONTENT}" > ${DEP_FILE}
}

# set -x

PATTERN='T [^ ]*\.o .*.o$'
if [[ "$@" =~ ${PATTERN} ]]; then
	TARGET_NAME=`echo "$@" | sed -e 's/.*T \([^ ]*\.o\) .*.o$/\1/'`
	TARGET_BC=`echo ${TARGET_NAME} | sed -e 's/\.o/\.bc/'`
	SOURCE_FILES=`echo "$@" | sed -e 's/.*T [^ ]*\.o \(.*.o\)$/\1/'`
fi

if [[ -n ${TARGET_NAME} ]]; then
	check_bc && llvm-link -o ${TARGET_BC} ${SOURCE_BCS} && llvm-dis ${TARGET_BC} \
		&& write_dep && ${ARCHIVE} "$@"
else
	${ARCHIVE} "$@"
fi
