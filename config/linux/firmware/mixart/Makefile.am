loader_dir = mixartloader
firmware_dir = mixart

cfg_files = miXart.conf
firmware_files = \
	miXart8AES.xlx \
	miXart8.elf \
	miXart8.xlx
loader_files = $(cfg_files) $(firmware_files)

EXTRA_DIST = $(loader_files)

include ../Makefile.loader
include ../Makefile.hotplug
