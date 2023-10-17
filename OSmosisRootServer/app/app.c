#include<sel4/sel4.h>
#include<utils/mk-printf.h>


#define __thread
seL4_IPCBuffer __sel4_ipc_buffer_obj;
__thread seL4_IPCBuffer *__sel4_ipc_buffer = &__sel4_ipc_buffer_obj;

int main(int argc, char **argv) {

       return    printf("process_2: hey hey hey\n");

}