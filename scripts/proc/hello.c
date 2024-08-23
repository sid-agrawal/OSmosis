#include <stdio.h>
#include <unistd.h>

int main() {
   printf("Hello?\n");
   
   // Idle until killed
   while(1) {
      sleep(10);
   }

   return 0;
}