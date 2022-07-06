From ubuntu:20.04

ARG DEBIAN_FRONTEND=noninteractive

RUN apt update && \
	apt upgrade -y && \
	apt install -y python3 wget python3-distutils sudo vim openssh-client libglib2.0-dev \
	libfdt-dev libpixman-1-dev zlib1g-dev libsasl2-dev libsdl2-dev libseccomp-dev \
	libsnappy-dev libssh-dev libvde-dev libvdeplug-dev libvte-2.91-dev libxen-dev \
	liblzo2-dev valgrind xfslibs-dev libnfs-dev libiscsi-dev libbluetooth-dev \
	libaio-dev libcurl4-gnutls-dev librbd-dev libnuma-dev libbrlapi-dev curl \
	linux-tools-common linux-tools-generic

RUN wget https://bootstrap.pypa.io/get-pip.py && \
	python3 get-pip.py && \
	pip install kconfiglib requests
