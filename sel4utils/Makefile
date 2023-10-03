ifeq ($(strip $(BUILD_DIR)),)
$(error BUILD_DIR must be specified)
endif


GCC_CPU := cortex-a53
TOOLCHAIN := aarch64-none-elf-
ARCH := aarch64



ifeq ($(ARCH),aarch64)
	C_FLAGS_ARCH := -mcpu=$(GCC_CPU) -mgeneral-regs-only
	ASM_CPP_FLAGS_ARCH := -mcpu=$(GCC_CPU)
	ASM_FLAGS_ARCH := -mcpu=$(GCC_CPU)
	ARCH_DIR := aarch64
else
	$(error ARCH must be aarch64)
endif

ifeq ($(strip $(SEL4CP_CONFIG)),)
$(error SEL4CP_CONFIG must be specified)
endif

BOARD_DIR := ../sel4cp/release/sel4cp-sdk-1.2.6/board/$(SEL4CP_BOARD)/$(SEL4CP_CONFIG)

C_FLAGS := -std=gnu11 -g3 -O3 -nostdlib -ffreestanding -Wall -Wno-maybe-uninitialized -Wno-unused-function -Werror \
		   -I$(SEL4_SDK)/include \
		   $(C_FLAGS_ARCH) \
		   -I$(BOARD_DIR)/include  \
		   -Iinclude/ \
		   -Iarch_include/arm/ \
		   -Isel4_arch_include/$(ARCH) \
		   -Isel4_arch/$(ARCH) \
		   -I../sel4vka/include \
		   -I../sel4vka/sel4_arch_include/$(ARCH) \
		   -I../sel4vka/arch_include/arm \
		   -I../sel4vspace/include \
		   -I../sel4vspace/arch_include/arm \
		   -I../utils/include \
		   -I../utils/arch_include/arm \
		   -I../sel4simple/arch_include/arm \
		   -I../sel4simple/include \
		   -I../sel4runtime/include \
		   -I../sel4runtime/include/sel4_arch/$(ARCH)


ASM_CPP_FLAGS := -x assembler-with-cpp -c -g3 $(ASM_CPP_FLAGS_ARCH)
ASM_FLAGS := -g3 $(ASM_FLAGS_ARCH)

ifeq ($(ARCH),x86_64)
	GCC := gcc
	AS := as
else
	GCC := $(TOOLCHAIN)gcc
	AS := $(TOOLCHAIN)as
endif

LIBS := libsel4utils.a
OBJS := elff.o mapping.o process.o profile.o arch.o slab.o stack.o strerror.o thread.o \
		bootstrap.o vspace.o \
		elf.o elf64.o elf32.o

$(BUILD_DIR)/libutils.a: ../utils/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN)- GCC_CPU=$(CPU) -C ../utils

$(BUILD_DIR)/libsel4simple.a: ../sel4simple/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN)- GCC_CPU=$(CPU) -C ../sel4simple

$(BUILD_DIR)/libsel4vspace.a: ../sel4vspace/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=$(BUILD_DIR) -C ../sel4vspace

$(BUILD_DIR)/%.o : src/%.c Makefile $(BUILD_DIR)/libsel4vspace.a $(BUILD_DIR)/libutils.a $(BUILD_DIR)/libsel4simple.a
	$(GCC) -c $(C_FLAGS) $< -o $@

$(BUILD_DIR)/%.o : src/vspace/%.c Makefile $(BUILD_DIR)/libsel4vspace.a $(BUILD_DIR)/libutils.a
	$(GCC) -c $(C_FLAGS) $< -o $@

$(BUILD_DIR)/%.o : src/elf/%.c Makefile $(BUILD_DIR)/libsel4vspace.a $(BUILD_DIR)/libutils.a
	$(GCC) -c $(C_FLAGS) $< -o $@

$(BUILD_DIR)/%.o : src/sel4_arch/$(ARCH)/%.c Makefile $(BUILD_DIR)/libsel4vspace.a $(BUILD_DIR)/libutils.a
	$(GCC) -c $(C_FLAGS) $< -o $@

LIB = $(addprefix $(BUILD_DIR)/, $(LIBS))

all: $(LIB)

$(LIB): $(addprefix $(BUILD_DIR)/, $(OBJS))
	$(TOOLCHAIN)ar -rv $@ $^
