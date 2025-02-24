#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>
#include <stdatomic.h>

#define BUFFER_SIZE 10

int buffer[BUFFER_SIZE];
int in = 0;
int out = 0;
int count = 0;
atomic_flag lock = ATOMIC_FLAG_INIT;

void acquire_lock() {
    while (atomic_flag_test_and_set(&lock)); // Busy wait until the lock is acquired
}

void release_lock() {
    atomic_flag_clear(&lock); // Release the lock
}

void *producer(void *param) {
    int item;
    while (1) {
        item = rand() % 100; // Produce an item

        acquire_lock();
        if (count < BUFFER_SIZE) {
            buffer[in] = item;
            in = (in + 1) % BUFFER_SIZE;
            atomic_fetch_add(&count, 1);
            printf("Produced: %d Buff Sz: %d\n", item, count);
        }
        release_lock();

        sleep(1 + rand() % 2); // Simulate time taken to produce an item (1 or 2 seconds)
    }
}

void *consumer(void *param) {
    int item;
    while (1) {
        acquire_lock();
        if (count > 0) {
            item = buffer[out];
            out = (out + 1) % BUFFER_SIZE;
            atomic_fetch_sub(&count, 1);
            printf("Consumed: %d Buff Sz: %d\n", item, count);
        }
        release_lock();

        sleep(1 + rand() % 2); // Simulate time taken to consume an item (1 or 2 seconds)
    }
}

#define MAX_KEYS 100

typedef struct {
    int key;
    int value;
} kv_pair;

kv_pair kv_store[MAX_KEYS];
int kv_count = 0;

int get(int key) {
    for (int i = 0; i < kv_count; i++) {
        if (kv_store[i].key == key) {
            return kv_store[i].value;
        }
    }
    return -1; // Key not found
}

void set(int key, int value) {
    for (int i = 0; i < kv_count; i++) {
        if (kv_store[i].key == key) {
            kv_store[i].value = value;
            return;
        }
    }
    if (kv_count < MAX_KEYS) {
        kv_store[kv_count].key = key;
        kv_store[kv_count].value = value;
        kv_count++;
    } else {
        printf("Key-Value store is full\n");
    }
}

int main() {
    pthread_t producer_thread, consumer_thread;

    // Create the producer and consumer threads
    pthread_create(&producer_thread, NULL, producer, NULL);
    pthread_create(&consumer_thread, NULL, consumer, NULL);

    // Wait for the threads to finish (they won't in this example)
    pthread_join(producer_thread, NULL);
    pthread_join(consumer_thread, NULL);

    return 0;
}