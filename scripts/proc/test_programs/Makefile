CC      = gcc
CFLAGS  = -Wall -O2

TARGETS = hello hello_shared_mem hello_static hello_file \
          hello_new_uid_ns hello_new_net_ns

.PHONY: all clean

all: $(TARGETS)

hello: hello.c
	$(CC) $(CFLAGS) -o $@ $<

hello_shared_mem: hello_shared_mem.c
	$(CC) $(CFLAGS) -o $@ $<

hello_static: hello_static.c
	$(CC) $(CFLAGS) -static -o $@ $<

hello_file: hello_file.c
	$(CC) $(CFLAGS) -o $@ $<

hello_new_uid_ns: hello_new_uid_ns.c
	$(CC) $(CFLAGS) -o $@ $<

hello_new_net_ns: hello_new_net_ns.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(TARGETS)
