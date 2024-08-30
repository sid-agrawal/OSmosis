#include <stdlib.h>
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/types.h>
#include <linux/nsfs.h>  /* Definition of NS_GET_NSTYPE */
#include <sys/ioctl.h>
#include <sys/stat.h>

/**
 * This file is not used for proc_model.py
 * It is just for exploration of namespaces
 */

int main() {
       pid_t pid = getpid();

       char pathname[128];
       sprintf(pathname, "/proc/%d/ns/mnt", pid);
       int fd = open(pathname, O_RDONLY);

       /*
       See: https://man7.org/linux/man-pages/man2/NS_GET_USERNS.2const.html
       */
       int user_ns_fd = ioctl(fd, NS_GET_USERNS);
       int parent_ns_fd = ioctl(fd, NS_GET_PARENT);
       int ns_type = ioctl(fd, NS_GET_NSTYPE);

       struct stat stat_buf;
       fstat(user_ns_fd, &stat_buf);

       printf("nstype: %d\n", ns_type);
       printf("user ns: fd %d\n", user_ns_fd);
       printf("parent ns: fd %d\n", parent_ns_fd);
       return 0;
}