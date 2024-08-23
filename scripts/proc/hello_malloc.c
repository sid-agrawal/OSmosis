#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#define MALLOC_SIZE 1024
int main() {
   // Allocate and access some memory
   void *mem = malloc(MALLOC_SIZE);
   printf("Hello! malloc'ed [%p,%p]\n", mem, mem + MALLOC_SIZE);

   int counter = 0;
   while (1) {
      counter = counter % 0x10000000;
      for (volatile int *i = mem; (void *) i < mem + MALLOC_SIZE; i++) {
         *i |= counter;
      }
   }

   return 0;
}