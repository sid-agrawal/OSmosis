#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>

int main(int argc, char **argv)
{
    int fd = atoi(argv[1]); // Get the FD to print to
    
    char buffer[64] = {};
    snprintf(buffer, sizeof(buffer), "Child PID in child ns: %d\n", getpid());
    write(fd, buffer, sizeof(buffer));

    // Idle until killed
    while (1)
    {
        sleep(10);
    }

    return 0;
}