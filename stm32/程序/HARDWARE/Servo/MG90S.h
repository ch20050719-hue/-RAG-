#ifndef MG90S_H
#define MG90S_H

#include <stdint.h>

#define MG90S_CMD_OPEN 0x09u
#define MG90S_CMD_CLOSE 0x0Au
#define MG90S_COMMAND_UNKNOWN 0u
#define MG90S_COMMAND_OPEN 1u
#define MG90S_COMMAND_CLOSE 2u

void MG90S_Init(void);
void MG90S_Open(void);
void MG90S_Close(void);
void MG90S_Tick1ms(void);
uint8_t MG90S_GetCommandedTarget(void);

#endif
