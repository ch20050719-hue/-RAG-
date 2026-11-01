#include <stdint.h>
#include "board.h"
/* Arm Compiler runtime performs scatter-loading before entering main(). */
extern void __main(void);
void Reset_Handler(void)
{
    __main();
    Default_Handler();
}
typedef void (*Vector)(void);
#define D Default_Handler
/* STM32F103 medium density: 16 core vectors + IRQ0..42. */
__attribute__((used, section("RESET"), aligned(256)))
const Vector vectors[59] = {
    (Vector)0x20005000u, Reset_Handler, D, D, D, D, D,
    0, 0, 0, 0, D, D, 0, D, SysTick_Handler,
    D, D, D, D, D, D, D, D, D, D, D, D, D, D, D, D,
    D, D, D, D, D, D, D, D, D, D, D, D, D, D, D, D,
    D, D, D, D, D, D, D, D, D, D, D
};
