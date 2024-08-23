#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <unistd.h>
#include <fcntl.h>

#define MMAP_SIZE 4096 * 3
#define MMAP_PATH "shm_path"

int main() {
   // create some shared memory
   int shm_fd = shm_open(MMAP_PATH, O_RDWR | O_CREAT, 0644);
   assert(shm_fd > 0);

   // map it
   ftruncate(shm_fd, MMAP_SIZE);
   void *mem = mmap(NULL, MMAP_SIZE, PROT_READ|PROT_WRITE, MAP_SHARED, shm_fd, 0);
   assert(mem != MAP_FAILED);

   printf("Hello! mmap'ed [%p,%p]\n", mem, mem + MMAP_SIZE);

   int counter = 0;
   while (1) {
      counter = counter % 0x10000000;
      for (volatile int *i = mem; (void *) i < mem + MMAP_SIZE; i++) {
         *i |= counter;
         counter++;
      }
   }

   return 0;
}