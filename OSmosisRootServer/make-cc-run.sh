rm -rf build ; mkdir build; 
cp ../../sel4/sel4-tutorials-manifest/dy-3_build/app build/app2.elf
bear --append --  make  BUILD_DIR=build  SEL4CP_SDK=../sel4cp/release/sel4cp-sdk-1.2.6  SEL4CP_CONFIG=debug  SEL4CP_BOARD=qemu_arm_virt ARCH=aarch64 run
