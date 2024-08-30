CC = gcc
CFLAGS = -Wall -Wextra -O2
STATIC_CFLAGS = $(CFLAGS) -static -static-libgcc -static-libstdc++
TARGETS = hello hello_malloc hello_mmap hello_static_1 hello_static_2 get_ns_info create_proc_in_ns hello_print_pid

all: $(TARGETS)

get_ns_info: get_ns_info.c
	$(CC) $(CFLAGS) -o get_ns_info get_ns_info.c

create_proc_in_ns: create_proc_in_ns.c
	$(CC) $(CFLAGS) -o create_proc_in_ns create_proc_in_ns.c

hello: hello.c
	$(CC) $(CFLAGS) -o hello hello.c

hello_print_pid: hello_print_pid.c
	$(CC) $(CFLAGS) -o hello_print_pid hello_print_pid.c

hello_static_1: hello.c
	$(CC) $(STATIC_CFLAGS) -o hello_static_1 hello.c

hello_static_2: hello_2.c
	$(CC) $(STATIC_CFLAGS) -o hello_static_2 hello_2.c

hello_malloc: hello_malloc.c
	$(CC) $(CFLAGS) -o hello_malloc hello_malloc.c

hello_mmap: hello_mmap.c
	$(CC) $(CFLAGS) -o hello_mmap hello_mmap.c

clean:
	rm -f $(TARGETS)

.PHONY: all clean