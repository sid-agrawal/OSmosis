#include<sel4/sel4.h>

seL4_IPCBuffer __sel4_ipc_buffer_obj;
__thread seL4_IPCBuffer *__sel4_ipc_buffer = &__sel4_ipc_buffer_obj;
int
main () {
        int x  = 2;
        return x;
}
