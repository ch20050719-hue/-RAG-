#pragma once

#include <cstdint>

// Times use esp_timer_get_time() microseconds; host tests supply a fake clock.
namespace conversation_timeout {
constexpr int64_t kSilenceUs = 8 * 1000000LL;
constexpr int64_t kResponseWaitUs = 60 * 1000000LL;

struct State {
    int64_t silence_since = -1;
    int64_t response_since = -1;
    bool replying = false;
    bool voice_active = false;
};

enum class Reason { None, Silence, ResponseTimeout };
struct Result {
    State state;
    Reason reason;
};

inline State Restart(State state, bool keep_voice) {
    return {-1, -1, false, keep_voice && state.voice_active};
}

inline State VoiceActivity(State state, int64_t now) {
    state.silence_since = -1;
    state.response_since = now;
    return state;
}

inline State VoiceChanged(State state, int64_t now, bool speaking, bool listening,
                          bool realtime_reply) {
    if (!listening && !realtime_reply) {
        return state;
    }
    state.voice_active = speaking;
    return listening ? VoiceActivity(state, now) : state;
}

inline State ReplyStarted(State state) {
    state.silence_since = -1;
    state.response_since = -1;
    state.replying = true;
    return state;
}

inline State ReplyFinished(State state, bool realtime = false) {
    state.silence_since = -1;
    state.response_since = -1;
    state.replying = false;
    if (!realtime) {
        state.voice_active = false;
    }
    return state;
}

inline Result Update(State state, int64_t now, bool enabled, bool voice, bool playback_idle) {
    if (!enabled || !playback_idle || state.replying) {
        state.silence_since = -1;
        return {state, Reason::None};
    }
    if (voice) {
        return {VoiceActivity(state, now), Reason::None};
    }
    if (state.response_since >= 0) {
        return {state, now - state.response_since >= kResponseWaitUs ? Reason::ResponseTimeout
                                                                     : Reason::None};
    }
    if (state.silence_since < 0) {
        state.silence_since = now;
    }
    return {state, now - state.silence_since >= kSilenceUs ? Reason::Silence : Reason::None};
}
}  // namespace conversation_timeout
