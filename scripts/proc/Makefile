CC = gcc
CFLAGS = -Wall -Wextra -O2
TARGETS = hello hello_malloc pagemap

all: $(TARGETS)

hello: hello.c
	$(CC) $(CFLAGS) -o hello hello.c

hello_malloc: hello_malloc.c
	$(CC) $(CFLAGS) -o hello_malloc hello_malloc.c

pagemap: pagemap.c
	$(CC) $(CFLAGS) -o pagemap pagemap.c

clean:
	rm -f $(TARGETS)

.PHONY: all clean