/*
 * Copyright 2021, Breakaway Consulting Pty. Ltd.
 *
 * SPDX-License-Identifier: BSD-2-Clause
 */

#define __thread

#include <stdint.h>
#include <sel4cp.h>
#include <allocator.h>
#include <elf/elf.h>

#include <simple/simple.h>
#include <sel4utils/process.h>
#include <allocman/bootstrap.h>
#include <allocman/vka.h>
#include <vka/capops.h>
#include <allocman/allocman.h>
#include <utils/mk-printf.h>
#include <utils/zf_log.h>
#include <simple-default/simple-default.h>

extern char _test_blob[];
extern char _test_blob_end[];

extern char _cpio_archive[];
extern char _cpio_archive_end[];

#define ALLOCATOR_VIRTUAL_POOL_SIZE ((1 << seL4_PageBits) * 4000)

/* allocator static pool */
#define ALLOCATOR_STATIC_POOL_SIZE ((1 << seL4_PageBits) * 20)

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

static bool is_loadable_section(const elf_t *elf_file, int index)
{
    return elf_getProgramHeaderType(elf_file, index) == PT_LOAD;
}

static int count_loadable_regions(const elf_t *elf_file)
{
    int num_headers = elf_getNumProgramHeaders(elf_file);
    int loadable_headers = 0;

    for (int i = 0; i < num_headers; i++) {
        /* Skip non-loadable segments (such as debugging data). */
        if (is_loadable_section(elf_file, i)) {
            loadable_headers++;
        }
    }
    return loadable_headers;
}


void test_symbols(){
     int error;
     sel4cp_dbg_puts("SYMBOLS\n");
     sel4cp_dbg_puts("_test_blob: ");
     puthex32((uint64_t)_test_blob);
     sel4cp_dbg_puts("\n");
     sel4cp_dbg_puts("_test_blob_end: ");
     puthex32((uint64_t)_test_blob_end);
     sel4cp_dbg_puts("\n");
     sel4cp_dbg_puts("_test_blob_size: ");
     puthex32((uint64_t)_test_blob_end - (uint64_t)_test_blob);
     sel4cp_dbg_puts("\n");

     elf_t elf_file ;
     error = elf_newFile(_test_blob, (uint64_t)_test_blob_end - (uint64_t)_test_blob, &elf_file);
     if (error) {
          sel4cp_dbg_puts("Error parsing elf file\n");
          puthex32(error);
          sel4cp_dbg_puts("\n");
     }
     int num_regions = count_loadable_regions(&elf_file);
     sel4cp_dbg_puts("Num reigons found: ");
     puthex32(num_regions);
     sel4cp_dbg_puts("\n");

     /*
          Create an allocator, it will need untyped info and
          first empty cslot
     */

     /*Adding this below makes it fails */
     uint64_t x = (uint64_t) sel4utils_allocated_object ;
     sel4cp_dbg_puts("FOun func simple_default_init_bootinfo: ");
     puthex32(x);
     sel4cp_dbg_puts("\n");
}
void test_malloc() {


     //char * c = NULL; malloc(100);
     for (int i = 0; i < 10; i++){

          char *c = malloc(1000);
          if (c == NULL)
          {
               printf("malloc failed\n");
          }
          else
          {
               printf("malloced: %p\n", c);
               for (int j = 0; j < 100; j++){
                    c[j] = 0x55;
               }
               printf("malloced memory is writeable and readable\n");
          }
     }
}

#define VIRTUAL_START (void *)0xA0000000
#define ALLOCATOR_VIRTUAL_POOL_SIZE ((1 << seL4_PageBits) * 4000)
#define ALLOCATOR_STATIC_POOL_SIZE ((1 << seL4_PageBits) * 20)
static char initial_mem_pool[ALLOCATOR_STATIC_POOL_SIZE];

/* stack for the new thread */
#define THREAD_2_STACK_SIZE 4096
UNUSED static char thread_2_stack[THREAD_2_STACK_SIZE];

/* function to run in the new thread */
void thread_2(void) {

     uint64_t x = (uint64_t) sel4utils_allocated_object ;
    /* TASK 15: print something */
    /* hint: printf() */

    printf("thread_2: hallo wereld %lx\n", x);
    /* never exit */
    while (1);
}

static vspace_t vspace;
static vka_t vka;
static sel4utils_alloc_data_t data;

static void init_allocator(vka_t *vka, vspace_t *vspace, sel4utils_alloc_data_t *data,
                           seL4_CPtr root_cnode, seL4_CPtr vspace_cap,
                           size_t cnode_size_bits, seL4_CPtr empty_slot_start, seL4_CPtr empty_slot_end,
                           size_t initial_mem_pool_size, void *initial_mem_pool)

{
     UNUSED int error;
     UNUSED reservation_t virtual_reservation;

     /* initialise allocator */
     allocman_t *allocator = bootstrap_use_current_1level(root_cnode,
                                                          cnode_size_bits,
                                                          empty_slot_start,
                                                          empty_slot_end,
                                                          initial_mem_pool_size,
                                                          initial_mem_pool);
     if (allocator == NULL)
     {
          ZF_LOGF("Failed to bootstrap allocator");
     }
     printf("---Bootstraped allocator\n");
     allocman_make_vka(vka, allocator);

     /* fill the allocator with untypeds */
     seL4_CPtr slot = 0x20;
     // unsigned int size_bits_index;
     // size_t size_bits;
     cspacepath_t path;
     //     for (slot = init_data->untypeds.start, size_bits_index = 0;
     //          slot <= init_data->untypeds.end;
     //          slot++, size_bits_index++) {

     vka_cspace_make_path(vka, slot, &path);
     /* allocman doesn't require the paddr unless we need to ask for phys addresses,
      * which we don't. */
     size_t size_bits = 29;
     path.capDepth = 10;
     error = allocman_utspace_add_uts(allocator, 1, &path, &size_bits, NULL,
                                      ALLOCMAN_UT_KERNEL);
     if (error)
     {
          ZF_LOGF("Failed to add untyped objects to allocator");
     }
     printf("---Add UTS\n");
     //     }

     /* add any arch specific objects to the allocator */
     //     arch_init_allocator(env, init_data);

     /* create a vspace */

     error = sel4utils_bootstrap_vspace(
         vspace,
         data,
         vspace_cap,
         vka,
         NULL, NULL, 0);
     if (error)
     {
          ZF_LOGF("Failed to bootstrap vspace");
     }
     printf("---VSpace Bootstrapped\n");

     /* switch the allocator to a virtual memory pool */
     virtual_reservation = vspace_reserve_range_at(vspace, VIRTUAL_START, ALLOCATOR_VIRTUAL_POOL_SIZE,
                                                   seL4_AllRights, 1);
     if (virtual_reservation.res == 0)
     {
          ZF_LOGF("Failed to switch allocator to virtual memory pool");
     }

     printf("---VSpace Range reserved\n");
     bootstrap_configure_virtual_pool(allocator, VIRTUAL_START, ALLOCATOR_VIRTUAL_POOL_SIZE, vspace_cap);
     printf("---Configured Virtual Pool\n");
}
void test_process_create() {

     /*
          Create an allocator
     */


    seL4_CPtr root_cnode = 0x7;
    size_t cnode_size_bits = 10;
    seL4_CPtr empty_slot_start = 0x40;
    seL4_CPtr empty_slot_end = 0x400;
    seL4_CPtr vspace_cap = 0x3;
#if 0
     int error;
     allocman_t *allocman;
    allocman = bootstrap_use_current_1level(root_cnode,
                                             cnode_size_bits,
                                             empty_slot_start,
                                             empty_slot_end,
                                            sizeof(initial_mem_pool),
                                            initial_mem_pool);

    assert(allocman);
    /* have to add all our resources manually */
    //for (i = bi->untyped.start; i < bi->untyped.end; i++) {
        cspacepath_t slot = allocman_cspace_make_path(allocman, 0x20);
        /*check for error*/
        cspacepath_t_print(&slot);
        slot.capDepth = 10;
        size_t size_bits = 29;
        uintptr_t paddr = 0x80000000;
        error = allocman_utspace_add_uts(allocman, 1, &slot, &size_bits, &paddr, ALLOCMAN_UT_KERNEL);
        assert(!error);
        printf("Added untyped no error\n");
   // }
//     error = allocman_fill_reserves(allocman);
//     assert(!error);

    /*
          Get a vka interface for the allcotor
    */
    allocman_make_vka(&vka, allocman);

   /*
          Get curent PDs CSpace and VSpace
   */
    //seL4_CPtr root_cnode = 0x7;

    error = sel4utils_bootstrap_vspace_leaky(&vspace, &data, vspace_cap, &vka, NULL);
     assert(error == 0);


    /* fill the allocator with virtual memory */
    UNUSED reservation_t virtual_reservation;
    virtual_reservation = vspace_reserve_range_at(&vspace, (void *)VIRTUAL_START,
                                                   ALLOCATOR_VIRTUAL_POOL_SIZE, seL4_AllRights, 1);
    printf("Reserved a chunk chunk of memory starting at: 0x%p \n", VIRTUAL_START);
    bootstrap_configure_virtual_pool(allocman, (void *) VIRTUAL_START,
                                      ALLOCATOR_VIRTUAL_POOL_SIZE, vspace_cap);

//     error = allocman_fill_reserves(allocman);
//     assert(!error);

    printf("Bootstraped virtual pool\n");
#endif
     printf("------Start: INIT ALLOCATOR----\n");
     init_allocator(&vka, &vspace, &data,
     root_cnode,
     vspace_cap,
     cnode_size_bits,
     empty_slot_start,
     empty_slot_end,
     sizeof(initial_mem_pool),
     initial_mem_pool);
     printf("------END: INIT ALLOCATOR----\n");
     /*
          Setup the config explictly
     */

    /*
         Get this for the confi
    */
    seL4_CPtr current_tcb = 0x06;
    seL4_CPtr current_sch_control=  0x21;
    seL4_CPtr current_asid_pool = 0x22;

    UNUSED sel4utils_process_config_t config = {
        .is_elf = true,
        .image_name = "app",
        .do_elf_load = true,
        //.entry_point = app_entrypoint,
        //.sysinfo = 0,

        .create_cspace = true,
        .one_level_cspace_size_bits = 12,
        //    .dest_cspace_tcb_cptr = ? ?,
        //    .cnode = ? ?,

        .create_vspace = true,
        .reservations = NULL,
        .num_reservations = 0,

        .create_fault_endpoint = true,
        .sched_params = {
          .create_sc = true,
          .auth = current_tcb,
          .sched_ctrl =  current_sch_control,
          .budget = 500000,
          .period = 500000,
          .priority = 254,
          .mcp = 254,
        },


        .asid_pool = current_asid_pool,
    };


     int error;
     //    vka_object_t root_pd = {0};
     //    error = vka_alloc_vspace_root(&vka, &root_pd);
     //    if (error) {
     //        ZF_LOGE("Failed to allocate page directory for new process: %d\n", error);
     //        return;
     //    } else {
     //        ZF_LOGE("Allocated page directory for new process: %x - Type 0x%x\n",
     //        root_pd.cptr,
     //        seL4_DebugCapIdentify(root_pd.cptr));
     //    }


    sel4utils_process_t new_process;
    error = sel4utils_configure_process_custom(&new_process, &vka, &vspace, config);
    if (error)
    {
         printf("Failed to configure new process.\n");
         assert(0);
    }
    else
    {
         printf("Success configuring new process.\n");
    }
     NAME_THREAD(new_process.thread.tcb.cptr, "app");
         printf("Success naming new process.\n");

#if 1

         /* create an endpoint */
         vka_object_t ep_object = {0};
         error = vka_alloc_endpoint(&vka, &ep_object);
         if (error)
         {
              ZF_LOGF("Failed to allocate new endpoint object.\n");
              assert(0);
         }
         cspacepath_t ep_cap_path;
         seL4_CPtr new_ep_cap = 0;
         vka_cspace_make_path(&vka, ep_object.cptr, &ep_cap_path);
         new_ep_cap = sel4utils_mint_cap_to_process(&new_process, ep_cap_path,
                                                    seL4_AllRights, ep_object.cptr);
          if (new_ep_cap == 0) {

         ZF_LOGF("Failed to mint a badged copy of the IPC endpoint into the new thread's CSpace.\n"
                                     "\tsel4utils_mint_cap_to_process takes a cspacepath_t: double check what you passed.\n");

          }


         printf("NEW CAP SLOT: %" PRIxPTR ".\n", ep_cap_path.capPtr);

         seL4_Word argc = 1;
         char string_args[argc][WORD_STRING_SIZE];
         char *argv[argc];
         sel4utils_create_word_args(string_args, argv, argc, 42);

         error = sel4utils_spawn_process_v(&new_process, &vka, &vspace, argc, (char **)&argv, 1);
         if (error)
         {
              ZF_LOGF("Failed to spawn and start the new thread.\n"
                      "\tVerify: the new thread is being executed in the root thread's VSpace.\n"
                      "\tIn this case, the CSpaces are different, but the VSpaces are the same.\n"
                      "\tDouble check your vspace_t argument.\n");

    }

    /* we are done, say hello */
    printf("main: hello world\n");
    seL4_DebugDumpScheduler();
    seL4_Yield();
    while(1);
#endif
}


void test_thread_create() {

     /*
          Create an allocator
     */

     int error;
    allocman_t *allocman;
    seL4_CPtr root_cnode = 0x7;
    size_t cnode_size_bits = 10;
    seL4_CPtr empty_slot_start = 0x40;
    seL4_CPtr empty_slot_end = 0x200;
    allocman = bootstrap_use_current_1level(root_cnode,
                                             cnode_size_bits,
                                             empty_slot_start,
                                             empty_slot_end,
                                            sizeof(initial_mem_pool),
                                            initial_mem_pool);

    assert(allocman);
    /* have to add all our resources manually */
    //for (i = bi->untyped.start; i < bi->untyped.end; i++) {
        cspacepath_t slot = allocman_cspace_make_path(allocman, 0x20);
        /*check for error*/
        cspacepath_t_print(&slot);
#if 1
        size_t size_bits = 29;
        uintptr_t paddr = 0x80000000;
        error = allocman_utspace_add_uts(allocman, 1, &slot, &size_bits, &paddr, ALLOCMAN_UT_KERNEL);
        assert(!error);
        printf("Added untyped no error\n");
   // }
//     error = allocman_fill_reserves(allocman);
//     assert(!error);
#endif

    /*
          Get a vka interface for the allcotor
    */
     vka_t vka;
    allocman_make_vka(&vka, allocman);

   /*
          Get curent PDs CSpace and VSpace
   */
    //seL4_CPtr root_cnode = 0x7;
    seL4_CPtr vspace = 0x3;



     /*
          Allocate new TCB
     */

        vka_object_t tcb_object = {0};
          int i = 0;
        error = vka_alloc_tcb(&vka, &tcb_object);
        if (error)
        {
             printf("[%d]Failed to allocate new TCB.\n"
                    "\tError  : %d\n:",
                    i, error);
        }
        else
        {
             printf("[%d]Success allocating TCB at slot: %lx, type: %d\n",
                    i,
                    tcb_object.cptr,
                    seL4_DebugCapIdentify(tcb_object.cptr));
        }

     /*
          Create scheduling context
     */
        vka_object_t sc_object = {0};

        error = vka_alloc_sched_context(&vka, &sc_object);
        if (error)
        {
             printf("[%d]Failed to allocate new SC.\n"
                    "\tError  : %d\n:",
                    i, error);
                    assert(0);
        }
        else
        {
             printf("[%d]Success allocating SC at slot: %lx, type: %d\n",
                    i,
                    sc_object.cptr,
                    seL4_DebugCapIdentify(sc_object.cptr));
        }

        error = seL4_SchedControl_Configure(0x21, sc_object.cptr, 1000000,1000000, 0,0);
        if (error)
        {
             printf("[%d]Failed to config new SC.\n"
                    "\tError  : %d\n:",
                    i, error);
                    assert(0);
        }
        else
        {
             printf("[%d]Success config SC at slot: %lx, type: %d\n",
                    i,
                    sc_object.cptr,
                    seL4_DebugCapIdentify(sc_object.cptr));
        }

        error = seL4_SchedContext_Bind(sc_object.cptr, tcb_object.cptr);
        if (error)
        {
             printf("[%d]Failed to bind new SC.\n"
                    "\tError  : %d\n:",
                    i, error);
                    assert(0);
        }
        else
        {
             printf("[%d]Success bind SC at slot: %lx, type: %d\n",
                    i,
                    sc_object.cptr,
                    seL4_DebugCapIdentify(sc_object.cptr));
        }

        /*
              Setup new TCB, CSpace, VSpace
        */

        error = seL4_TCB_Configure(tcb_object.cptr, root_cnode,
                                   64 - 10, // guard
                                   vspace, seL4_NilData, 0, 0);
        if (error)
        {
             printf("Failed to configure the new TCB object. Error (%d)\n"
                    "\tWe're running the new thread with the root thread's CSpace.\n"
                    "\tWe're running the new thread in the root thread's VSpace.\n"
                    "\tWe will not be executing any IPC in this app.\n",
                    error);
        }

        /*
              Setup new priority, entry, stack-pointer etc.
        */
        seL4_CPtr current_tcb = 0x06;
        NAME_THREAD(current_tcb, "OSmosisRootServer");
        error = seL4_TCB_SetPriority(tcb_object.cptr, current_tcb, 254);
        if (error)
        {
             printf("Failed to set the priority for the new TCB object.\n");
        }

        /* TASK 10: give the new thread a name */
        /* hint: we've done thread naming before */

        NAME_THREAD(tcb_object.cptr, "dynamic-1: thread_2");

        UNUSED seL4_UserContext regs = {0};
        sel4utils_set_instruction_pointer(&regs, (seL4_Word)thread_2);

        /* check that stack is aligned correctly */
        const int stack_alignment_requirement = sizeof(seL4_Word) * 2;
        uintptr_t thread_2_stack_top = (uintptr_t)thread_2_stack + sizeof(thread_2_stack) - 8;
        printf("thread_2_stack_top: %lx\n", thread_2_stack_top);
        printf("stack size: %lx\n", sizeof(thread_2_stack));
        printf("stack_alignment_requirement: %x\n", stack_alignment_requirement);
        //     for (int i = 0; i < 10* sizeof(thread_2_stack); i++){
        //          thread_2_stack[i]= 0x55;
        //          printf("Wrote %c at location %d\n" , thread_2_stack[i], i);
        //     }

        if (thread_2_stack_top % (stack_alignment_requirement) != 0)
        {
             printf("Stack top (%lx) isn't aligned correctly to a %dB boundary.\n"
                    "\tDouble check to ensure you're not trampling.",
                    thread_2_stack_top,
                    stack_alignment_requirement);
        }
        sel4utils_set_stack_pointer(&regs, thread_2_stack_top);

        error = seL4_TCB_WriteRegisters(tcb_object.cptr, 0, 0, 2, &regs);
        if (error)
        {
             printf("Failed with error (%d)to write the new thread's register set.\n"
                    "\tDid you write the correct number of registers? See arg4.\n",
                    error);
        }
        /*
               Start the thread
          */
        error = seL4_TCB_Resume(tcb_object.cptr);
        if (error)
        {
             printf("Failed (%d) to start new thread.\n", error);
    }
    printf("other thread started\n");
    seL4_Yield();
    seL4_DebugDumpScheduler();

    }

seL4_BootInfo bootInfo;
void populateBootInfo(){
     seL4_BootInfo *bi = &bootInfo;

     bi->nodeID = 0;
     bi->numNodes = 1;
     bi->numIOPTLevels = 0;
     bi->initThreadCNodeSizeBits = 12;

     /* Untyped Array */
     bi->untyped.start = 0x20;
     bi->untyped.end = 0x21;


     /* User Frame Array */

     /* User PT Array */



}

void
init(void)
{

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
     // We can set the guard to be (64 - foo) bits.
     int foo = 10;

     int error = seL4_CNode_Mint(7,
                       0x17,
                       foo,
                       7,
                       0x7,
                      foo,
                       seL4_AllRights,
                       64 - foo);
    if (error) {
        sel4cp_dbg_puts("Error minting cnode cap to add guard\n");
        puthex32(error);
        sel4cp_dbg_puts("\n");
    } else {
        sel4cp_dbg_puts("Success minting cnode cap to add guard\n");
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

     /*
     0x20 untyped
     0x21 sched control
     0x22 asid pool*/

     seL4_Word seL4_Fault_SendUntyped = 21;
     // Send a message to the monitor asking for an untyped.
     seL4_MessageInfo_t msg = seL4_MessageInfo_new(seL4_Fault_SendUntyped, 0, 0, 0);

     // Set receipt path
     for (int i = 0; i < 3; i++) {
          seL4_SetCapReceivePath(7, 0x20 + i, foo);
          msg = seL4_Call(MONITOR_ENDPOINT_CAP, msg);
          if (seL4_MessageInfo_get_extraCaps(msg) != 1)
          {
               assert(0);
               /* Die*/
               sel4cp_dbg_puts("Did not receive cap from monitor. CapNum:\n");
               puthex32(seL4_MessageInfo_get_extraCaps(msg));
               sel4cp_dbg_puts("\n");
               sel4cp_dbg_puts("Error Code:");
               puthex32(seL4_MessageInfo_get_label(msg));
               sel4cp_dbg_puts("\n");
          }
          else
          {
               sel4cp_dbg_puts("Got cap\n");
               puthex32(0x20 + i);
               sel4cp_dbg_puts("> ");
               puthex32(seL4_DebugCapIdentify(0x20 + i));
               sel4cp_dbg_puts("\n");
          }
}

     for (int i = 0; i < 0x25 ;i++){
          puthex32(i);
          sel4cp_dbg_puts("> ");
          puthex32(seL4_DebugCapIdentify(i));
          if (i == 0x20) {
                sel4cp_dbg_puts("<--");
          }
          sel4cp_dbg_puts("\n");

     }

#if 0
    // Let's retype that cap.
    error = seL4_Untyped_Retype(0x20,
                                    seL4_UntypedObject,  /*type*/
                                    20, /*size*/
                                    7, /*root cnode*/
                                    0, /*address fro the root */
                                    0, /*depth for this last address*/
                                    0x21, /*offset*/
                                    1);
     if (error) {
          sel4cp_dbg_puts("Error retypeing cap\n");
          puthex32(error);
          sel4cp_dbg_puts("\n");
     } else {
          sel4cp_dbg_puts("Success retypeing cap\n");
     }


#endif

     for (int i = 0x20; i < 0x30 ;i++){
          puthex32(i);
          sel4cp_dbg_puts("> ");
          puthex32(seL4_DebugCapIdentify(i));
          if (i == 0x20) {
                sel4cp_dbg_puts("<--");
          }
          sel4cp_dbg_puts("\n");

     }




//     error =  seL4_CNode_Mint(
//                /* _service */    7,//  dest->root,
//                /* dest_index */  0x25,//  dest->capPtr,
//                /* destDepth */   10,// dest->capDepth,
//                /* src_root */    7,//  src->root,
//                /* src_index */   0x21,//  src->capPtr,
//                /* src_depth */   10,//  src->capDepth,
//                /* rights */      seL4_AllRights,
//                /* badge  */        0
//            );
//      for (int i = 0x20; i < 0x30 ;i++){
//           puthex32(i);
//           sel4cp_dbg_puts("> ");
//           puthex32(seL4_DebugCapIdentify(i));
//           if (i == 0x20) {
//                 sel4cp_dbg_puts("<--");
//           }
//           sel4cp_dbg_puts("\n");

//      }

     //test_symbols();
     //test_malloc10();
     // populateBootInfo();
     //test_thread_create();
     test_process_create();
}
void
notified(sel4cp_channel ch)
{
}