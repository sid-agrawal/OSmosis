#include <stdint.h>
#include <stdbool.h>
#include <sel4cp.h>
#include <stddef.h>
#include "printf.h"
#include "wordle.h"

/*
 * Here we initialise the word to "hello", but later in the tutorial
 * we will actually randomise the word the user is guessing.
 */
char word[WORD_LENGTH] = { 'h', 'e', 'l', 'l', 'o' };

#define CLIENT_CHANNEL 1
#define VMM_CHANNEL 2

bool is_character_in_word(char *word, int ch) {
    for (int i = 0; i < WORD_LENGTH; i++) {
        if (word[i] == ch) {
            return true;
        }
    }

    return false;
}

enum character_state char_to_state(int ch, char *word, uint64_t index) {
    if (ch == word[index]) {
        return CORRECT_PLACEMENT;
    } else if (is_character_in_word(word, ch)) {
        return INCORRECT_PLACEMENT;
    } else {
        return INCORRECT;
    }
}

void init(void) {
    sel4cp_dbg_puts("WORDLE SERVER: starting\n");
}

void notified(sel4cp_channel channel) {}

sel4cp_msginfo protected(sel4cp_channel channel, sel4cp_msginfo msginfo)
{
    switch (channel) {
        case CLIENT_CHANNEL:
            for (int i = 0; i < WORD_LENGTH; i++) {
                char ch = sel4cp_mr_get(i);
                sel4cp_mr_set(i, char_to_state(ch, word, i));
            }
            return sel4cp_msginfo_new(0, WORD_LENGTH);
            break;
        case VMM_CHANNEL:
            for (int i = 0; i < WORD_LENGTH; i++) {
                word[i] = sel4cp_mr_get(i);
            }
            break;
        default:
            sel4cp_dbg_puts("ERROR!\n");
            break;
    }

    return sel4cp_msginfo_new(0, 0);
}
