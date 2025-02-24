
#include <stdio.h>

#define MAX_KEYS 100

typedef struct {
    int key;
    int value;
} kv_pair;

kv_pair kv_store[MAX_KEYS];
int kv_count = 0;

int get(int key) {
    printf("\tgetting key: %d\n", key);
    for (int i = 0; i < kv_count; i++) {
        if (kv_store[i].key == key) {
            return kv_store[i].value;
        }
    }
    return -1; // Key not found
}

void set(int key, int value) {
    printf("\tSetting key: %d, value: %d\n", key, value);
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