#ifndef TEST_USART_SYS_H
#define TEST_USART_SYS_H
#include <stdint.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef struct { uint32_t SR; uint32_t DR; } USART_TypeDef;
typedef struct { int port; } GPIO_TypeDef;
extern USART_TypeDef test_usarts[3];
extern GPIO_TypeDef test_gpio[2];
#define USART1 (&test_usarts[0])
#define USART2 (&test_usarts[1])
#define USART3 (&test_usarts[2])
#define USART_FLAG_PE 0x01u
#define USART_FLAG_FE 0x02u
#define USART_FLAG_NE 0x04u
#define USART_FLAG_ORE 0x08u
#define USART_FLAG_RXNE 0x20u
#define USART_IT_ERR 3
#define GPIOA (&test_gpio[0])
#define GPIOB (&test_gpio[1])
enum { RESET = 0, DISABLE = 0, ENABLE = 1, GPIO_Speed_50MHz = 50,
       GPIO_Mode_AF_PP = 1, GPIO_Mode_IN_FLOATING = 2,
       USART1_IRQn = 1, USART2_IRQn = 2, USART3_IRQn = 3,
       USART_WordLength_8b = 8, USART_StopBits_1 = 1, USART_Parity_No = 0,
       USART_HardwareFlowControl_None = 0, USART_Mode_Rx = 1, USART_Mode_Tx = 2,
       USART_IT_RXNE = 1, USART_IT_TXE = 2 };
#define GPIO_Pin_2 (1u << 2)
#define GPIO_Pin_3 (1u << 3)
#define GPIO_Pin_9 (1u << 9)
#define GPIO_Pin_10 (1u << 10)
#define GPIO_Pin_11 (1u << 11)
#define RCC_APB2Periph_GPIOA 1u
#define RCC_APB2Periph_GPIOB 2u
#define RCC_APB2Periph_USART1 4u
#define RCC_APB1Periph_USART2 8u
#define RCC_APB1Periph_USART3 16u
typedef struct { uint32_t GPIO_Pin; int GPIO_Speed, GPIO_Mode; } GPIO_InitTypeDef;
typedef struct {
    int NVIC_IRQChannel, NVIC_IRQChannelPreemptionPriority;
    int NVIC_IRQChannelSubPriority, NVIC_IRQChannelCmd;
} NVIC_InitTypeDef;
typedef struct {
    uint32_t USART_BaudRate;
    int USART_WordLength, USART_StopBits, USART_Parity;
    int USART_HardwareFlowControl, USART_Mode;
} USART_InitTypeDef;
void RCC_APB1PeriphClockCmd(uint32_t bits, int enable);
void RCC_APB2PeriphClockCmd(uint32_t bits, int enable);
void GPIO_Init(GPIO_TypeDef *port, GPIO_InitTypeDef *config);
void NVIC_Init(NVIC_InitTypeDef *config);
void USART_Init(USART_TypeDef *uart, USART_InitTypeDef *config);
void USART_ITConfig(USART_TypeDef *uart, int interrupt, int enable);
void USART_Cmd(USART_TypeDef *uart, int enable);
int USART_GetITStatus(USART_TypeDef *uart, int interrupt);
void USART_SendData(USART_TypeDef *uart, uint16_t value);
uint8_t USART_ReceiveData(USART_TypeDef *uart);
uint32_t __get_PRIMASK(void);
void __disable_irq(void);
void __set_PRIMASK(uint32_t value);
#endif
