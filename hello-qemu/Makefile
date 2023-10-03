#
# Copyright 2021, Breakaway Consulting Pty. Ltd.
#
# SPDX-License-Identifier: BSD-2-Clause
#
ifeq ($(strip $(BUILD_DIR)),)
$(error BUILD_DIR must be specified)
endif

ifeq ($(strip $(SEL4CP_SDK)),)
$(error SEL4CP_SDK must be specified)
endif

ifeq ($(strip $(SEL4CP_CONFIG)),)
$(error SEL4CP_CONFIG must be specified)
endif

TOOLCHAIN := aarch64-none-elf

CPU := cortex-a53

CC := $(TOOLCHAIN)-gcc
LD := $(TOOLCHAIN)-ld
AS := $(TOOLCHAIN)-as
SEL4CP_TOOL ?= $(SEL4CP_SDK)/bin/sel4cp
SEL4CP_BOARD := qemu_arm_virt

HELLO_OBJS := hello.o global_data.o

BOARD_DIR := $(SEL4CP_SDK)/board/$(SEL4CP_BOARD)/$(SEL4CP_CONFIG)

IMAGES := hello.elf
CFLAGS := -mcpu=$(CPU) -mstrict-align -nostdlib -ffreestanding -g3 -O3 -Wall  -Wno-unused-function -Werror \
	  -I$(BOARD_DIR)/include \
	  -I../libosmosis/include \
	  -I../sel4vka/include \
	  -I../sel4allocman/include \
	  -I../sel4simple/include \
	  -I../sel4utils/include

LDFLAGS := -L$(BOARD_DIR)/lib -L$(BUILD_DIR)
LIBS := -lsel4cp -Tsel4cp.ld
OSLIBS := -losmosis -lsel4vka -lsel4allocman -lsel4utils -lutils


IMAGE_FILE = $(BUILD_DIR)/loader.img
REPORT_FILE = $(BUILD_DIR)/report.txt

all: $(IMAGE_FILE)


$(BUILD_DIR)/app.elf: app/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=`pwd`/$(BUILD_DIR) -C ./app

$(BUILD_DIR)/global_data.o: global_data.S Makefile $(BUILD_DIR)/app.elf
	$(CC) -c -g3 -DBLOB_PATH=\"/bin/ls\"  -x assembler-with-cpp  $< -o $@

$(BUILD_DIR)/libutils.a: ../utils/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=`pwd`/$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN)- GCC_CPU=$(CPU) -C ../utils

$(BUILD_DIR)/libsel4utils.a: ../sel4utils/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=`pwd`/$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN)- GCC_CPU=$(CPU) -C ../sel4utils `pwd`/build/libsel4utils.a

$(BUILD_DIR)/libsimple.a: ../sel4simple/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=`pwd`/$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN)- GCC_CPU=$(CPU) -C ../sel4simple

$(BUILD_DIR)/libsel4vka.a: ../sel4vka/Makefile $(BUILD_DIR)/libutils.a
	$(MAKE) ARCH=aarch64 BUILD_DIR=`pwd`/$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN)- GCC_CPU=$(CPU) -C ../sel4vka

$(BUILD_DIR)/libsel4allocman.a: ../sel4allocman/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=`pwd`/$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN)- GCC_CPU=$(CPU) -C ../sel4allocman `pwd`/build/libsel4allocman.a

$(BUILD_DIR)/libosmosis.a: ../libosmosis/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=`pwd`/$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN)- GCC_CPU=$(CPU) -C ../libosmosis


$(BUILD_DIR)/%.o: %.c Makefile $(BUILD_DIR)/libutils.a $(BUILD_DIR)/libsel4vka.a $(BUILD_DIR)/libsel4allocman.a $(BUILD_DIR)/libosmosis.a $(BUILD_DIR)/libsimple.a $(BUILD_DIR)/libsel4utils.a
	$(CC) -c $(CFLAGS) $< -o $@

$(BUILD_DIR)/%.o: %.s Makefile $(BUILD_DIR)/libutils.a $(BUILD_DIR)/libsel4vka.a $(BUILD_DIR)/libsel4allocman.a $(BUILD_DIR)/libosmosis.a
	$(AS) -g3 -mcpu=$(CPU) $< -o $@

$(BUILD_DIR)/hello.elf: $(addprefix $(BUILD_DIR)/, $(HELLO_OBJS)) $(BUILD_DIR)/libutils.a $(BUILD_DIR)/libsel4vka.a $(BUILD_DIR)/libsel4allocman.a $(BUILD_DIR)/libosmosis.a
	$(LD) $(LDFLAGS) $^ $(LIBS) $(OSLIBS) -o $@

$(IMAGE_FILE) $(REPORT_FILE): $(addprefix $(BUILD_DIR)/, $(IMAGES)) hello.system
	$(SEL4CP_TOOL) hello.system --search-path $(BUILD_DIR) --board $(SEL4CP_BOARD) --config $(SEL4CP_CONFIG) -o $(IMAGE_FILE) -r $(REPORT_FILE)

run: $(IMAGE_FILE)
	qemu-system-aarch64 -machine virt,virtualization=on \
		-cpu $(CPU) \
		-serial mon:stdio \
		-device loader,file=$(IMAGE_FILE),addr=0x70000000,cpu-num=0 \
		-m size=2G \
		-nographic \
		-netdev user,id=mynet0 \
		-device virtio-net-device,netdev=mynet0,mac=52:55:00:d1:55:01
clean:
	rm -rf $(BUILD_DIR)/*