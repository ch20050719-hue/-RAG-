#include "usart.h"
#include <string.h>

/* Exercise production usart.c and voice_command.c, replacing only hardware. */
void uart3_init(u32 bound);
void USART1_IRQHandler(void);
void USART2_IRQHandler(void);
void USART3_IRQHandler(void);
USART_TypeDef test_usarts[3];
GPIO_TypeDef test_gpio[2];
volatile uint32_t g_tim3_heartbeat;
static uint32_t apb1, apb2, primask, disable_count, restore_count;
static GPIO_InitTypeDef pins[2][16];
static USART_InitTypeDef uart_configs[3];
static NVIC_InitTypeDef irq_configs[4];
static int rx_enabled[3], uart_enabled[3], rx_pending[3];
static uint8_t giz_bytes[8];
static uint32_t giz_count;
static int failures;
#define CHECK(value) do { if (!(value)) { puts("FAIL: " #value); ++failures; } } while (0)

void RCC_APB1PeriphClockCmd(uint32_t bits, int enable) { if (enable) apb1 |= bits; }
void RCC_APB2PeriphClockCmd(uint32_t bits, int enable) { if (enable) apb2 |= bits; }
void GPIO_Init(GPIO_TypeDef *port, GPIO_InitTypeDef *config) {
    unsigned bit;
    for (bit = 0; bit < 16; ++bit) {
        if (config->GPIO_Pin & (1u << bit)) pins[port == GPIOB][bit] = *config;
    }
}
void NVIC_Init(NVIC_InitTypeDef *config) { irq_configs[config->NVIC_IRQChannel] = *config; }
void USART_Init(USART_TypeDef *uart, USART_InitTypeDef *config) { uart_configs[uart - test_usarts] = *config; }
void USART_ITConfig(USART_TypeDef *uart, int interrupt, int enable) {
    CHECK(interrupt == USART_IT_RXNE); rx_enabled[uart - test_usarts] = enable;
}
void USART_Cmd(USART_TypeDef *uart, int enable) { uart_enabled[uart - test_usarts] = enable; }
int USART_GetITStatus(USART_TypeDef *uart, int interrupt) {
    CHECK(interrupt == USART_IT_RXNE); return rx_pending[uart - test_usarts];
}
uint8_t USART_ReceiveData(USART_TypeDef *uart) {
    rx_pending[uart - test_usarts] = 0; return (uint8_t)uart->DR;
}
uint32_t __get_PRIMASK(void) { return primask; }
void __disable_irq(void) { primask = 1; ++disable_count; }
void __set_PRIMASK(uint32_t value) { primask = value; ++restore_count; }
void gizPutData(uint8_t *data, uint32_t length) {
    CHECK(length == 1); if (giz_count < sizeof giz_bytes) giz_bytes[giz_count++] = *data;
}
static void byte(unsigned port, uint8_t value) {
    test_usarts[port].DR = value; rx_pending[port] = 1; ++g_tim3_heartbeat;
    if (port == 0) USART1_IRQHandler();
    else if (port == 1) USART2_IRQHandler();
    else USART3_IRQHandler();
}
static void frame(unsigned port, uint8_t command) {
    byte(port, 0xF4); byte(port, 0x06); byte(port, command); byte(port, 0xFB);
}
static void test_configuration(void) {
    uart1_init(9600); uart2_init(9600); uart3_init(9600);
    CHECK((apb1 & (RCC_APB1Periph_USART2 | RCC_APB1Periph_USART3)) ==
                 (RCC_APB1Periph_USART2 | RCC_APB1Periph_USART3));
    CHECK((apb2 & (RCC_APB2Periph_USART1 | RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB)) ==
                 (RCC_APB2Periph_USART1 | RCC_APB2Periph_GPIOA | RCC_APB2Periph_GPIOB));
    CHECK(pins[1][10].GPIO_Mode == GPIO_Mode_AF_PP);
    CHECK(pins[1][10].GPIO_Speed == GPIO_Speed_50MHz);
    CHECK(pins[1][11].GPIO_Mode == GPIO_Mode_IN_FLOATING);
    CHECK(pins[0][9].GPIO_Mode == GPIO_Mode_AF_PP && pins[0][10].GPIO_Mode == GPIO_Mode_IN_FLOATING);
    CHECK(pins[0][2].GPIO_Mode == GPIO_Mode_AF_PP && pins[0][3].GPIO_Mode == GPIO_Mode_IN_FLOATING);
    CHECK(uart_configs[2].USART_BaudRate == 9600);
    CHECK(uart_configs[2].USART_WordLength == USART_WordLength_8b);
    CHECK(uart_configs[2].USART_StopBits == USART_StopBits_1);
    CHECK(uart_configs[2].USART_Parity == USART_Parity_No);
    CHECK(uart_configs[2].USART_HardwareFlowControl == USART_HardwareFlowControl_None);
    CHECK(uart_configs[2].USART_Mode == (USART_Mode_Rx | USART_Mode_Tx));
    CHECK(rx_enabled[0] && rx_enabled[1] && rx_enabled[2]);
    CHECK(uart_enabled[0] && uart_enabled[1] && uart_enabled[2]);
    CHECK(irq_configs[3].NVIC_IRQChannelCmd == ENABLE);
    CHECK(irq_configs[1].NVIC_IRQChannelPreemptionPriority == irq_configs[3].NVIC_IRQChannelPreemptionPriority);
}
static void test_independent_streams(void) {
    uint8_t command = 0;
    byte(0, 0xF4); byte(0, 0x06);
    byte(2, 0x09); byte(2, 0xFB);
    CHECK(!USART1_TakeCommand(&command)); /* Cross-UART fragments cannot form a frame. */
    byte(0, 0x01); byte(0, 0xFB);
    CHECK(USART1_TakeCommand(&command) && command == 1);
    byte(0, 0xF4); byte(2, 0xF4); byte(0, 0x06); byte(2, 0x06);
    byte(0, 0x02); byte(2, 0x0A); byte(0, 0xFB); byte(2, 0xFB);
    CHECK(USART1_TakeCommand(&command));
    CHECK(command == 2 || command == 10);
    { uint8_t first = command;
      CHECK(USART1_TakeCommand(&command)); CHECK(command != first && (command == 2 || command == 10)); }
    CHECK(!USART1_TakeCommand(&command));
}
static void test_fairness_and_modes(void) {
    uint8_t result[6] = {0}, command, i;
    for (i = 1; i <= 3; ++i) { frame(0, i); frame(2, (uint8_t)(i + 8)); }
    for (i = 0; i < 6; ++i) CHECK(USART1_TakeCommand(&result[i]));
    for (i = 1; i < 6; ++i) CHECK((result[i] < 8) != (result[i - 1] < 8));
    for (i = 2; i < 6; ++i) CHECK(result[i] == result[i - 2] + 1);
    CHECK(!USART1_TakeCommand(&command));
    for (i = 1; i <= 12; ++i) {
        frame(2, i); CHECK(USART1_TakeCommand(&command) && command == i);
    }
    CHECK(!USART1_TakeCommand(&command));
    frame(2, 0); frame(2, 13); CHECK(!USART1_TakeCommand(&command));
    frame(2, 8); CHECK(!USART1_TakeCommand(0));
    CHECK(USART1_TakeCommand(&command) && command == 8);
    primask = 1; CHECK(!USART1_TakeCommand(&command)); CHECK(primask == 1);
    primask = 0; CHECK(!USART1_TakeCommand(&command)); CHECK(primask == 0);
    CHECK(disable_count > 0 && disable_count == restore_count);
}
static void test_cloud_unchanged(void) {
    uint8_t command;
    frame(1, 8);
    CHECK(giz_count == 4 && giz_bytes[0] == 0xF4 && giz_bytes[1] == 6 &&
          giz_bytes[2] == 8 && giz_bytes[3] == 0xFB);
    CHECK(!USART1_TakeCommand(&command));
    USART3_IRQHandler(); CHECK(!USART1_TakeCommand(&command));
}
int main(void) {
    test_configuration(); test_independent_streams(); test_fairness_and_modes(); test_cloud_unchanged();
    if (!failures) puts("USART1/USART3 isolation, fairness, configuration and USART2 regression passed");
    return failures ? 1 : 0;
}
