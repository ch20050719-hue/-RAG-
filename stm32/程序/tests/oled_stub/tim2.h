#ifndef TEST_OLED_TIM2_H
#define TEST_OLED_TIM2_H
#include <stdint.h>
extern uint8_t modeee;
#define HOME_SCENE_NORMAL 0u
#define HOME_SCENE_SLEEP 1u
#define HOME_SCENE_AWAY 2u
void HomeScene_Apply(uint8_t scene);
uint8_t HomeScene_GetCurrent(void);
#endif
