#ifndef __MENU_H
#define __MENU_H

#include "stm32f10x.h"                  // Device header
#include "oled.h"
#include "dht11.h"
//#include "gizwits_product.h"

extern u8 Humi;
extern u8 Temp;
extern uint16_t Lux;
extern u8 Menu;
extern uint16_t Smoke;

void Menu1(void);
void Menu11(void);

void Menu2(void);
void OLED_Option(u8 num);


void OLED_Option_open(u8 num);
void OLED_controlDevicePage1(void);
void OLED_controlDevicePage2(void);
void OLED_controlDoorPage(void);
void ControlDeviceSwitch(uint8_t selection, uint8_t page);

#endif
