#define NORETURN            __attribute__((noreturn))
#define UNREACHABLE()       __builtin_unreachable()

NORETURN void abort(void);
