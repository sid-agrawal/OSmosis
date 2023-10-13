
#
# Copyright 2021, Breakaway Consulting Pty. Ltd.
#
# SPDX-License-Identifier: BSD-2-Clause
#
ifeq ($(strip $(BUILD_DIR)),)
$(error BUILD_DIR must be specified)
endif

ifeq ($(strip $(SEL4CP_CONFIG)),)
$(error SEL4CP_CONFIG must be specified)
endif

TOOLCHAIN := aarch64-none-elf

CPU := cortex-a53

CC := $(TOOLCHAIN)-gcc
LD := $(TOOLCHAIN)-ld
AS := $(TOOLCHAIN)-as
SEL4CP_BOARD := qemu_arm_virt

APP_OBJS := app.o

BOARD_DIR := ../../sel4cp/release/sel4cp-sdk-1.2.6/board/$(SEL4CP_BOARD)/$(SEL4CP_CONFIG)

IMAGES := app.elf
CFLAGS := -mcpu=$(CPU) -mstrict-align -nostdlib -ffreestanding -g3 -O3 -Wall  -Wno-unused-function -Werror \
		-I$(BOARD_DIR)/include \
		-I../../sel4runtime/include
LDFLAGS := -L$(BOARD_DIR)/lib -L$(BUILD_DIR)
LIBS := # -lsel4cp
OSLIBS := -lsel4runtime


all: $(BUILD_DIR)/app.elf

$(BUILD_DIR)/libsel4runtime.a: ../../sel4runtime/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN)- GCC_CPU=$(CPU) -C ../../sel4runtime

$(BUILD_DIR)/%.o: %.c Makefile $(BUILD_DIR)/libsel4runtime.a
	$(CC) -c $(CFLAGS) $< -o $@

$(BUILD_DIR)/%.o: %.s Makefile
	$(AS) -g3 -mcpu=$(CPU) $< -o $@

$(BUILD_DIR)/app.elf: $(addprefix $(BUILD_DIR)/, $(APP_OBJS))
	$(LD) $(LDFLAGS) $^ $(LIBS) $(OSLIBS) -o $@
