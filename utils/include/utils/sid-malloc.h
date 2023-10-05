#pragma once

/*
 * Simple defs for
 * malloc
 * calloc
 * free
 * strlen
 */



void *malloc (size_t);
void *calloc (size_t, size_t);
void free (void *);
size_t strlen(const char *str);