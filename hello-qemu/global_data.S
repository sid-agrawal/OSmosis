/* @ivanv: need to consider the case where not all of these are used! */
/* @probits is used to say that this section contains data. */
/* The attributes "aw" is to say that the section is allocatable and that it is writeable. */

#if defined(BLOB_PATH)
.section .test_blob, "aw", @progbits
.global _test_blob, _test_blob_end
_test_blob:
.incbin BLOB_PATH
_test_blob_end:
#endif

/*
if defined(VM_KERNEL_IMAGE_PATH)
.section .guest_kernel_image, "aw", @progbits
.global _guest_kernel_image, _guest_kernel_image_end
_guest_kernel_image:
.incbin VM_KERNEL_IMAGE_PATH
_guest_kernel_image_end:
#endif
*/


/*

$(BUILD_DIR)/package_guest_images.o: $(VMM_TOOLS)/package_guest_images.S $(IMAGE_DIR) $(LINUX) $(INITRD) $(DTB)
	$(CC) -c -g3 -x assembler-with-cpp \
					-DGUEST_KERNEL_IMAGE_PATH=\"$(LINUX)\" \
					-DGUEST_DTB_IMAGE_PATH=\"$(DTB)\" \
					-DGUEST_INITRD_IMAGE_PATH=\"$(INITRD)\" \
					$< -o $@


*/