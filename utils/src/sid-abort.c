#include<utils/sid-abort.h>
#include<utils/mk-printf.h>
/*
 * overwrite the default implementation for abort()
 */
void NORETURN abort(void)
{
    printf("HALT due to call to abort()\n");

    /* We could call the SBI shutdown now. However, it's likely there is an
     * issue that needs to be debugged. Instead of doing a busy loop, spinning
     * over a wfi is the better choice here, as it allows the core to enter an
     * idle state until something happens.
     */
    for (;;) {
        asm volatile("wfi" ::: "memory");
    }

    UNREACHABLE();
}
