#include<sel4/sel4.h>
#include<utils/mk-printf.h>

seL4_IPCBuffer __sel4_ipc_buffer_obj;
__thread seL4_IPCBuffer *__sel4_ipc_buffer = &__sel4_ipc_buffer_obj;
int
main () {
       while(1);
       printf("Hello World\n");
}
