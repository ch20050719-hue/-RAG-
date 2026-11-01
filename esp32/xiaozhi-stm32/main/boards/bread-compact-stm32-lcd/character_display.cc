#include "character_display.h"
#include "application.h"
#include "character_animation_policy.h"
#include "display/lvgl_display/lvgl_image.h"

extern const uint8_t character_idle_start[] asm("_binary_character_idle_gif_start");
extern const uint8_t character_idle_end[] asm("_binary_character_idle_gif_end");
extern const uint8_t character_talking_start[] asm("_binary_character_talking_gif_start");
extern const uint8_t character_talking_end[] asm("_binary_character_talking_gif_end");

CharacterDisplay::CharacterDisplay(esp_lcd_panel_io_handle_t panel_io, esp_lcd_panel_handle_t panel,
                                   int width, int height, int offset_x, int offset_y, bool mirror_x,
                                   bool mirror_y, bool swap_xy)
    : SpiLcdDisplay(panel_io, panel, width, height, offset_x, offset_y, mirror_x, mirror_y,
                    swap_xy) {
    DisplayLockGuard lock(this);
    character_timer_ = lv_timer_create(
        [](lv_timer_t* timer) {
            static_cast<CharacterDisplay*>(lv_timer_get_user_data(timer))->RefreshCharacter();
        },
        100, this);
    if (character_timer_ == nullptr) {
        ESP_LOGE("CharacterDisplay", "Unable to create character animation timer");
    }
}

CharacterDisplay::~CharacterDisplay() {
    DisplayLockGuard lock(this);
    if (character_timer_ != nullptr) {
        lv_timer_delete(character_timer_);
        character_timer_ = nullptr;
    }
}

void CharacterDisplay::SetEmotion(const char*) {
    // Cloud emotions and theme initialization retain the selected character.
    DisplayLockGuard lock(this);
    RefreshCharacter();
}

void CharacterDisplay::RefreshCharacter() {
    if (!setup_ui_called_ || emoji_image_ == nullptr)
        return;
    if (preview_image_ != nullptr && !lv_obj_has_flag(preview_image_, LV_OBJ_FLAG_HIDDEN))
        return;
    if (character_loaded_) {
        lv_obj_add_flag(emoji_label_, LV_OBJ_FLAG_HIDDEN);
        lv_obj_remove_flag(emoji_image_, LV_OBJ_FLAG_HIDDEN);
    }
    auto& app = Application::GetInstance();
    const auto state = app.GetDeviceState();
    const bool speech_state = state == kDeviceStateSpeaking || state == kDeviceStateNotifying;
    const bool next_talking = character_animation::ShouldTalk(
        speech_state, talking_, app.GetAudioService().IsPlaybackIdle());
    if (character_loaded_ && next_talking == talking_)
        return;
    if (load_failed_ && lv_tick_elaps(last_failure_tick_) < 5000)
        return;
    if (LoadCharacter(next_talking)) {
        talking_ = next_talking;
        character_loaded_ = true;
        load_failed_ = false;
    } else {
        load_failed_ = true;
        last_failure_tick_ = lv_tick_get();
    }
}

bool CharacterDisplay::LoadCharacter(bool talking) {
    const uint8_t* begin = talking ? character_talking_start : character_idle_start;
    const uint8_t* end = talking ? character_talking_end : character_idle_end;
    LvglRawImage image(const_cast<uint8_t*>(begin), static_cast<size_t>(end - begin));
    auto next_controller = std::make_unique<LvglGif>(image.image_dsc());
    if (!next_controller->IsLoaded()) {
        ESP_LOGE("CharacterDisplay", "Unable to load %s animation", talking ? "talking" : "idle");
        return false;  // Preserve the previous valid frame/controller.
    }
    if (gif_controller_)
        gif_controller_->Stop();
    // Replace LVGL's source before releasing the previous frame buffer.
    lv_image_set_src(emoji_image_, next_controller->image_dsc());
    gif_controller_ = std::move(next_controller);
    gif_controller_->SetFrameCallback(
        [this]() { lv_image_set_src(emoji_image_, gif_controller_->image_dsc()); });
    lv_obj_add_flag(emoji_label_, LV_OBJ_FLAG_HIDDEN);
    lv_obj_remove_flag(emoji_image_, LV_OBJ_FLAG_HIDDEN);
    gif_controller_->Start();
    return true;
}
