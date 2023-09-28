ifeq ($(strip $(BUILD_DIR)),)
$(error BUILD_DIR must be specified)
endif

ifeq ($(strip $(GCC_CPU)),)
$(error GCC_CPU must be specified)
endif

ifeq ($(strip $(ARCH)),)
$(error ARCH must be specified)
endif

ifeq ($(strip $(TOOLCHAIN)),)
$(error TOOLCHAIN must be specified)
endif

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
		   -Iinclude/mode/64/ \
		   -I$(BOARD_DIR)/include  \
		   -Iinclude/sel4_arch/$(ARCH_DIR) \
		   -I../sel4utils/include


ASM_CPP_FLAGS := -x assembler-with-cpp -c -g3 $(ASM_CPP_FLAGS_ARCH)
ASM_FLAGS := -g3 $(ASM_FLAGS_ARCH)

ifeq ($(ARCH),x86_64)
	GCC := gcc
	AS := as
else
	GCC := $(TOOLCHAIN)gcc
	AS := $(TOOLCHAIN)as
endif

LIBS := libsel4allocman.a
OBJS := allocman.o bootstrap.o \
		simple1level.o single_level.o two_level.o \
		dual_pool.o fixed_pool.o k_r_malloc.o malloc.o virtual_pool.o vspace_pool.o \
		split.o twinkle.o

$(BUILD_DIR)/libsel4utils.a: ../sel4utils/Makefile
	$(MAKE) ARCH=aarch64 BUILD_DIR=$(BUILD_DIR) TOOLCHAIN=$(TOOLCHAIN) GCC_CPU=$(GCC_CPU) -C ../sel4utils

$(BUILD_DIR)/%.o : src/%.c Makefile $(BUILD_DIR)/libsel4utils.a
	$(GCC) -c $(C_FLAGS) $< -o $@

$(BUILD_DIR)/%.o : src/cspace/%.c Makefile $(BUILD_DIR)/libsel4utils.a
	$(GCC) -c $(C_FLAGS) $< -o $@

$(BUILD_DIR)/%.o : src/mspace/%.c Makefile $(BUILD_DIR)/libsel4utils.a
	$(GCC) -c $(C_FLAGS) $< -o $@

$(BUILD_DIR)/%.o : src/utspace/%.c 	Makefile $(BUILD_DIR)/libsel4utils.a
	$(GCC) -c $(C_FLAGS) $< -o $@

LIB = $(addprefix $(BUILD_DIR)/, $(LIBS))

all: $(LIB)

$(LIB): $(addprefix $(BUILD_DIR)/, $(OBJS))
	$(TOOLCHAIN)ar -rv $@ $^
