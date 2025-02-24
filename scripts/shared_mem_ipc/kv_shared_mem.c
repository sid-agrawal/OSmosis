#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <string.h>
#include <stdatomic.h>
#include <unistd.h>
#include <time.h>
#include "kv_inmemory.h"


typedef enum {
    GET,
    SET
} message_type_t;
typedef struct {
    message_type_t cmd;
    int key;
    int value;
    atomic_int message_ready;
    atomic_int result_ready;
    int result;
} shared_buffer_t;

void *thread1_func(void *arg) {
    shared_buffer_t *shared_buffer = (shared_buffer_t *)arg;
    const char *messages[] = {"SET key value", "GET key"};
    int message_index = 0;

    while (1) {
        shared_buffer->cmd = rand() % 2 == 0 ? GET : SET;
        if (shared_buffer->cmd == SET) {
            shared_buffer->key = rand() %10;
            shared_buffer->value = rand() %100;
        } else {
            shared_buffer->key = rand() %10;
        }
        atomic_store(&shared_buffer->message_ready, 1);

        while (!atomic_load(&shared_buffer->result_ready)) {
            // Busy-wait
        }
        if (shared_buffer->cmd == SET) {
            printf("SET: Success\n");
        } else {
            if (shared_buffer->result != -1 ) {
                printf("GET: Success. Value : %d\n", shared_buffer->result);
            } else {
                printf("GET: Error : %d\n", shared_buffer->result);
            }
        }
        atomic_store(&shared_buffer->result_ready, 0);

        // Sleep for a random time between 1 and 2 seconds
        sleep(1 + rand() % 2);
    }

    return NULL;
}

void *thread2_func(void *arg) {
    shared_buffer_t *shared_buffer = (shared_buffer_t *)arg;

    while (1) {
        while (!atomic_load(&shared_buffer->message_ready)) {
            // Busy-wait
        }
        char key_str[20];
        sprintf(key_str, "%d", shared_buffer->key);

        char value_str[20];
        if (shared_buffer->cmd == SET) {
            sprintf(value_str, "%d", shared_buffer->value);
        } else {
            sprintf(value_str, "NA");
        }
        // printf("Thread 2 received message: %s %s %s\n", 
        //     shared_buffer->cmd == GET ? "GET" : "SET",
        //     key_str, value_str);
        atomic_store(&shared_buffer->message_ready, 0);

        if (shared_buffer->cmd == SET) {
            set(shared_buffer->key, shared_buffer->value);
            shared_buffer->result = 0; // Indicate success
        } else if (shared_buffer->cmd == GET) {
            shared_buffer->result = get(shared_buffer->key);
        }

        atomic_store(&shared_buffer->result_ready, 1);

        // Sleep for a random time between 1 and 2 seconds
        sleep(1 + rand() % 2);
    }

    return NULL;
}

int main() {
    pthread_t thread1, thread2;
    shared_buffer_t shared_buffer;

    atomic_init(&shared_buffer.message_ready, 0);
    atomic_init(&shared_buffer.result_ready, 0);

    srand(time(NULL)); // Seed the random number generator

    pthread_create(&thread1, NULL, thread1_func, &shared_buffer);
    pthread_create(&thread2, NULL, thread2_func, &shared_buffer);

    pthread_join(thread1, NULL);
    pthread_join(thread2, NULL);

    return 0;
}
