/*
 * Copyright 2021, Breakaway Consulting Pty. Ltd.
 *
 * SPDX-License-Identifier: BSD-2-Clause
 */
#include <stdint.h>
#include <sel4cp.h>
#include <allocator.h>

extern char _test_blob[];
extern char _test_blob_end[];

static char
hexchar(unsigned int v)
{
    return v < 10 ? '0' + v : ('a' - 10) + v;
}

void
puthex32(uint32_t val)
{
    char buffer[8 + 3];
    buffer[0] = '0';
    buffer[1] = 'x';
    buffer[8 + 3 - 1] = 0;
    for (unsigned i = 8 + 1; i > 1; i--) {
        buffer[i] = hexchar(val & 0xf);
        val >>= 4;
    }
    sel4cp_dbg_puts(buffer);
}

void
init(void)
{

     foobar(4);
     sel4cp_dbg_puts("hello, world\n");
     //seL4_DebugSnapshot();
     for (int i = 0; i < 0x20; i++){
          puthex32(i);
          sel4cp_dbg_puts("> ");
          puthex32(seL4_DebugCapIdentify(i));
          if (i == 0x16) {
                sel4cp_dbg_puts("<--");
          }
          sel4cp_dbg_puts("\n");

     }
     for (int i = 0; i < 0x21 ;i++){
          puthex32(i);
          sel4cp_dbg_puts("> ");
          puthex32(seL4_DebugCapIdentify(i));
          if (i == 0x20) {
                sel4cp_dbg_puts("<--");
          }
          sel4cp_dbg_puts("\n");

     }
     // We can set the guard to be (64 - 9) bits.

     int error = seL4_CNode_Mint(7,
                       0x17,
                       9,
                       7,
                       0x7,
                       9,
                       seL4_AllRights,
                       64 - 9);
    if (error) {
        sel4cp_dbg_puts("Error minting cnode cap to add guard\n");
        puthex32(error);
        sel4cp_dbg_puts("\n");
    }
        sel4cp_dbg_puts("Success minting cnode cap to add guard\n");

     for (int i = 0; i < 0x21 ;i++){
          puthex32(i);
          sel4cp_dbg_puts("> ");
          puthex32(seL4_DebugCapIdentify(i));
          if (i == 0x20) {
                sel4cp_dbg_puts("<--");
          }
          sel4cp_dbg_puts("\n");

     }


     seL4_Word seL4_Fault_SendUntyped = 21;
     // Send a message to the monitor asking for an untyped.
     seL4_MessageInfo_t msg = seL4_MessageInfo_new(seL4_Fault_SendUntyped, 0, 0, 0);

     // Set receipt path
     seL4_SetCapReceivePath(7, 0x20, 9);
     msg = seL4_Call(MONITOR_ENDPOINT_CAP, msg);
     if (seL4_MessageInfo_get_extraCaps(msg) != 1) {
          /* Die*/
          sel4cp_dbg_puts("Did not receive cap from monitor. CapNum:\n");
          puthex32(seL4_MessageInfo_get_extraCaps(msg));
          sel4cp_dbg_puts("\n");
          sel4cp_dbg_puts("Error Code:");
          puthex32(seL4_MessageInfo_get_label(msg));
          sel4cp_dbg_puts("\n");
     }
          sel4cp_dbg_puts("Got cap\n");

     for (int i = 0; i < 0x21 ;i++){
          puthex32(i);
          sel4cp_dbg_puts("> ");
          puthex32(seL4_DebugCapIdentify(i));
          if (i == 0x20) {
                sel4cp_dbg_puts("<--");
          }
          sel4cp_dbg_puts("\n");

     }

#if 1
    // Let's retype that cap.
    error = seL4_Untyped_Retype(0x20,
                                    seL4_UntypedObject,  /*type*/
                                    29, /*size*/
                                    7, /*root cnode*/
                                    0, /*address fro the root */
                                    0, /*depth for this last address*/
                                    0x21, /*offset*/
                                    1);
     if (error) {
          sel4cp_dbg_puts("Error retypeing cap\n");
          puthex32(error);
          sel4cp_dbg_puts("\n");
     }
          sel4cp_dbg_puts("Success retypeing cap\n");


#endif

     for (int i = 0x20; i < 0x25 ;i++){
          puthex32(i);
          sel4cp_dbg_puts("> ");
          puthex32(seL4_DebugCapIdentify(i));
          if (i == 0x20) {
                sel4cp_dbg_puts("<--");
          }
          sel4cp_dbg_puts("\n");

     }



}

void
notified(sel4cp_channel ch)
{
}