#include<sel4/sel4.h>

__thread seL4_IPCBuffer *__sel4_ipc_buffer;
int 
main () {
        int x  = 2;
        return x;
}
