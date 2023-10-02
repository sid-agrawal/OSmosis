/*
 * Copyright 2017, Data61, CSIRO (ABN 41 687 119 230)
 *
 * SPDX-License-Identifier: BSD-2-Clause
 */

#pragma once

typedef int millicelcius_t;
typedef unsigned int millikelvin_t;
typedef int celcius_t;
typedef unsigned int kelvin_t;

/* The canonical temperature unit is millikelvin */
typedef millikelvin_t temperature_t;

/* Temperature Conversions */
#define MILLIKELVIN_OFFSET 273150

#define MILLIKELVIN_IN_KELVIN      1000
#define MILLICELCIUS_IN_CELCIUS    1000

/* Coverts from a millicelcius to millikelvin
 * Behaviour when given a value less than -237150 (absolute zero)
 * is undefined.
 */
static inline millikelvin_t millicelcius_to_millikelvin(millicelcius_t mc) {
    return mc + MILLIKELVIN_OFFSET;
}

/* Converts from millikelvin to millicelcius */
static inline millicelcius_t millikelvin_to_millicelcius(millikelvin_t mk) {
    return mk - MILLIKELVIN_OFFSET;
}

/* Converts from celcius to kelvin */
static inline kelvin_t celcius_to_kelvin(celcius_t c) {
    return millicelcius_to_millikelvin(c * MILLICELCIUS_IN_CELCIUS) / MILLIKELVIN_IN_KELVIN;
}

/* Converts from kelvin to celcius */
static inline celcius_t kelvin_to_celcius(kelvin_t k) {
    return millikelvin_to_millicelcius(k * MILLIKELVIN_IN_KELVIN) / MILLICELCIUS_IN_CELCIUS;
}
