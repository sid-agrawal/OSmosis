#define _GNU_SOURCE
#ifndef __USE_GNU
#define __USE_GNU
#endif
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sched.h>
#include <fcntl.h>

/**
 * This file is not used for proc_model.py
 * It is just for exploration of namespaces
 *
 * Must be called as root in order to create new namespaces
 */

char fd_buffer[16];

int main(int argc, char **argv)
{
    printf("Running create_proc_in_ns\n");

    if (argc < 2)
    {
        fprintf(stderr, "error: needs program name and output filename as arguments\n");
        return -1;
    }

    char *program_name = argv[1];
    char *output_file = argv[2];

    // Open the log file
    int fd = open(output_file, O_CREAT | O_RDWR, S_IRWXO);
    dup2(fd, fileno(stdout));

    // Create the new namespace with unshare
    int result = unshare(CLONE_NEWPID);
    if (result == -1)
    {
        fprintf(stderr, "error: creating new namespace: %d, %s\n", errno, strerrorname_np(errno));
        return -1;
    }

    // Start the process
    pid_t pid = fork();
    if (pid == 0)
    {
        printf("Starting process `%s` in new namespace\n", program_name);
        snprintf(fd_buffer, sizeof(fd_buffer), "%d", fd);
        static char *argv[] = {"hello", fd_buffer, NULL}; // Pass the fd buffer to write
        execv(program_name, argv);
        fprintf(stderr, "error: execv failed\n");
    }
    else
    {
        printf("Child PID in parent ns: %d\n", pid);
        close(fd);
        waitpid(pid, 0, 0);
    }

    return 0;
}