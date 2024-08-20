CC = gcc
CFLAGS = -Wall -Wextra -O2
TARGETS = hello1 hello2

all: $(TARGETS)

hello1: hello1.c
	$(CC) $(CFLAGS) -o hello1 hello1.c

hello2: hello2.c
	$(CC) $(CFLAGS) -o hello2 hello2.c

clean:
	rm -f $(TARGETS)

.PHONY: all clean