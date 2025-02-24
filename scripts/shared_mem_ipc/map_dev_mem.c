#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <stdint.h>
#include <string.h>

#define PHYS_ADDR 0x20000000  // Replace with the desired physical address
#define MAP_SIZE 4096UL       // Size of the memory to map
#define MAP_MASK (MAP_SIZE - 1)

void send_message(void *virt_addr, const char *message) {
    // Write the message to the shared memory region
    strncpy((char *)virt_addr, message, MAP_SIZE);
}

int main() {
    int fd;
    void *map_base, *virt_addr;
    uint32_t read_result;

    // Open /dev/mem
    if ((fd = open("/dev/mem", O_RDWR | O_SYNC)) == -1) {
        perror("Error opening /dev/mem");
        exit(EXIT_FAILURE);
    }

    // Map the physical address to virtual address space
    map_base = mmap(0, MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, PHYS_ADDR & ~MAP_MASK);
    if (map_base == (void *) -1) {
        perror("Error mapping memory");
        close(fd);
        exit(EXIT_FAILURE);
    }

    // Calculate the virtual address
    virt_addr = map_base + (PHYS_ADDR & MAP_MASK);

    // Send a message to the shared memory region
    send_message(virt_addr, "Hello from process 1!");

    // Read from the mapped memory
    read_result = *((uint32_t *) virt_addr);
    printf("Value at physical address 0x%X: 0x%X\n", PHYS_ADDR, read_result);

    // Clean up
    if (munmap(map_base, MAP_SIZE) == -1) {
        perror("Error unmapping memory");
    }
    close(fd);

    return 0;
}