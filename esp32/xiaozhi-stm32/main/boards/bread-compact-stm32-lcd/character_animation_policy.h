#pragma once

namespace character_animation {
inline bool ShouldTalk(bool speech_state, bool already_talking, bool playback_idle) {
    return speech_state || (already_talking && !playback_idle);
}
}  // namespace character_animation
