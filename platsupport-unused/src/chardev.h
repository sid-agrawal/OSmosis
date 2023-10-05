/*
 * Copyright 2017, Data61, CSIRO (ABN 41 687 119 230)
 *
 * SPDX-License-Identifier: BSD-2-Clause
 */

#pragma once

#include <platsupport/chardev.h>
#include <utils/arith.h>

struct dev_defn {
    enum chardev_id id;
    uintptr_t paddr;
    int size;
    const int *irqs;
    int (*init_fn)(const struct dev_defn *defn,
                   const ps_io_ops_t *ops,
                   struct ps_chardevice *dev);
};

static inline void *chardev_map(
    const struct dev_defn *dev,
    const ps_io_ops_t *ops)
{
    return ps_io_map(
               &ops->io_mapper,
               dev->paddr,
               dev->size,
               0, // map uncached
               PS_MEM_NORMAL);
}

int uart_init(
    const struct dev_defn *defn,
    const ps_io_ops_t *ops,
    ps_chardevice_t *dev);

int uart_static_init(
    void *vaddr,
    const ps_io_ops_t *ops,
    ps_chardevice_t *dev);

ssize_t uart_write(
    ps_chardevice_t *dev,
    const void *vdata,
    size_t count,
    chardev_callback_t rcb UNUSED,
    void *token UNUSED);

ssize_t uart_read(
    ps_chardevice_t *dev,
    void *vdata,
    size_t count,
    chardev_callback_t rcb UNUSED,
    void *token UNUSED);

int uart_getchar(
    ps_chardevice_t *dev);

int uart_putchar(
    ps_chardevice_t *dev,
    int c);

