#pragma once
#include "display/lcd_display.h"

// Instantiated only by bread-compact-stm32-lcd.
class CharacterDisplay : public SpiLcdDisplay {
public:
    CharacterDisplay(esp_lcd_panel_io_handle_t panel_io, esp_lcd_panel_handle_t panel, int width,
                     int height, int offset_x, int offset_y, bool mirror_x, bool mirror_y,
                     bool swap_xy);
    ~CharacterDisplay() override;
    void SetEmotion(const char* emotion) override;

private:
    lv_timer_t* character_timer_ = nullptr;
    bool talking_ = false;
    bool character_loaded_ = false;
    bool load_failed_ = false;
    uint32_t last_failure_tick_ = 0;
    void RefreshCharacter();
    bool LoadCharacter(bool talking);
};
