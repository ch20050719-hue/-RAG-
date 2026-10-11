# STM32 UART control board

Based on bread-compact-wifi-lcd, ESP32-S3, ST7735 128x160.
Audio/display wiring is inherited and must match the physical board.
The example GPIO lamp is replaced by STM32 MCP tools.
UART1 TX GPIO17, RX GPIO18, 9600 8N1; STM32F103C8T6 USART3 RX PB11, TX PB10.
See [integration and validation](../../../docs/STM32控制接入.md).

## Animated character

CharacterDisplay is local to this board and reuses LvglGif. Embedded assets are 96x96: character_idle.gif blinks every 4.15 seconds; character_talking.gif cycles mouth poses every 160ms while speaking/notifying and until playback tails drain. Cloud emotion updates retain the character. The physical screen remains 128x160 and UART/audio/display pins are unchanged.

Run tests/run-character-animation-tests.ps1, tests/run-conversation-timeout-tests.ps1, tests/run-stm32-control-tests.ps1 and the documented board build. The STM32 project also keeps a real gifdec.c host decoder test at tests/xiaozhi-character/decoder/run-tests.ps1. Physical playback/animation coexistence and PSRAM free heap still require device testing.