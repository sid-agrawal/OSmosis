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
		   -Iinclude/ \
		   -Iarch_include/arm/ \
		   -I$(BOARD_DIR)/include  \
		   -I../utils/include \
		   -I../utils/arch_include/arm/ \
		   -I../sel4vka/include


ASM_CPP_FLAGS := -x assembler-with-cpp -c -g3 $(ASM_CPP_FLAGS_ARCH)
ASM_FLAGS := -g3 $(ASM_FLAGS_ARCH)

ifeq ($(ARCH),x86_64)
	GCC := gcc
	AS := as
else
	GCC := $(TOOLCHAIN)gcc
	AS := $(TOOLCHAIN)as
endif

LIBS := libsimple.a
OBJS := simple.o

$(BUILD_DIR)/%.o : src/%.c Makefile
	$(GCC) -c $(C_FLAGS) $< -o $@

LIB = $(addprefix $(BUILD_DIR)/, $(LIBS))

all: $(LIB)

$(LIB): $(addprefix $(BUILD_DIR)/, $(OBJS))
	$(TOOLCHAIN)ar -rv $@ $^
