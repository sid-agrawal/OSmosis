#include <stdint.h>
#include <stdio.h>
#include <sel4cp.h>
#include "printf.h"

// This variable will have the address of the UART device
uintptr_t uart_base_vaddr;
uintptr_t ip_buffer;
uintptr_t op_buffer;

#define RHR_MASK 0b111111111
#define UARTDR 0x000
#define UARTFR 0x018
#define UARTIMSC 0x038
#define UARTICR 0x044
#define PL011_UARTFR_TXFF (1 << 5)
#define PL011_UARTFR_RXFE (1 << 4)

#define REG_PTR(base, offset) ((volatile uint32_t *)((base) + (offset)))

void uart_init() {
    *REG_PTR(uart_base_vaddr, UARTIMSC) = 0x50;
}

int uart_get_char() {
    int ch = 0;

    if ((*REG_PTR(uart_base_vaddr, UARTFR) & PL011_UARTFR_RXFE) == 0) {
        ch = *REG_PTR(uart_base_vaddr, UARTDR) & RHR_MASK;
    }

    return ch;
}

void uart_put_char(int ch) {
    while ((*REG_PTR(uart_base_vaddr, UARTFR) & PL011_UARTFR_TXFF) != 0);

    *REG_PTR(uart_base_vaddr, UARTDR) = ch;
    if (ch == '\r') {
        uart_put_char('\n');
    }
}

void uart_handle_irq() {
    *REG_PTR(uart_base_vaddr, UARTICR) = 0x7f0;
}

void uart_put_str(char *str) {
    while (*str) {
        uart_put_char(*str);
        str++;
    }
}

void init(void) {
    // First we initialise the UART device, which will write to the
    // device's hardware registers. Which means we need access to
    // the UART device.
    uart_init();
    // After initialising the UART, print a message to the terminal
    // saying that the serial server has started.
    uart_put_str("SERIAL SERVER: starting\n");
}


#define IRQ_CHANNEL_ID 0
#define RECEIVER_CHANNEL_ID 1

void notified(sel4cp_channel channel) {
    switch (channel) {
        case IRQ_CHANNEL_ID:
            int ch = uart_get_char();
            uart_put_char(ch);
            uart_handle_irq();

            // Convey the char to the client
            *((char *)ip_buffer) = ch;
            sel4cp_notify(RECEIVER_CHANNEL_ID);
            sel4cp_irq_ack(channel);
        case RECEIVER_CHANNEL_ID:
            // Read data from ip_buffer
            // uart_put_str("Received message from client\n");
            char c = *((char *)op_buffer);
            uart_put_char(c);
            break;
        default:
            break;
    }
}
