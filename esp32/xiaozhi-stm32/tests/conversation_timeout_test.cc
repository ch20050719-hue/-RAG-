#include "conversation_timeout.h"
#include <cstdio>
#include <cstdlib>

static unsigned checks = 0;
#define CHECK(x)                                                 \
    do {                                                         \
        ++checks;                                                \
        if (!(x)) {                                              \
            std::fprintf(stderr, "FAIL %d: %s\n", __LINE__, #x); \
            std::exit(1);                                        \
        }                                                        \
    } while (0)

int main() {
    using namespace conversation_timeout;
    State state;
    auto poll = [&](int64_t now, bool enabled = true, bool voice = false, bool idle = true) {
        auto result = Update(state, now, enabled, voice, idle);
        state = result.state;
        return result.reason;
    };
    CHECK(poll(0) == Reason::None);
    CHECK(poll(7999999) == Reason::None);
    CHECK(poll(8000000) == Reason::Silence);
    state = {};
    CHECK(poll(100000000) == Reason::None);  // A new conversation gets a fresh interval.
    state = VoiceActivity(state, 107000000);
    CHECK(poll(120000000, true, true) == Reason::None);  // Long speech.
    state = VoiceActivity(state, 121000000);             // Speech ends, wait for the server.
    CHECK(poll(130000000) == Reason::None);              // STT can be late.
    state = VoiceActivity(state, 140000000);             // Nonempty STT / new user activity.
    CHECK(poll(199999999) == Reason::None);
    CHECK(poll(200000000) == Reason::ResponseTimeout);
    state = ReplyStarted(state);
    CHECK(poll(300000000) == Reason::None);  // AI speaking is never a silence timeout.
    state = ReplyFinished(state);
    CHECK(poll(301000000, true, false, false) == Reason::None);
    CHECK(poll(320000000, true, false, false) == Reason::None);  // Long playback tail.
    CHECK(poll(321000000) == Reason::None);
    CHECK(poll(328999999) == Reason::None);
    CHECK(poll(329000000) == Reason::Silence);
    state = {};
    CHECK(poll(0, false) == Reason::None);  // Manual / no VAD / disconnected.
    CHECK(poll(9000000, false) == Reason::None);
    CHECK(poll(10000000) == Reason::None);
    CHECK(poll(17999999) == Reason::None);
    CHECK(poll(18000000) == Reason::Silence);
    state = {};
    CHECK(poll(0) == Reason::None);
    state = VoiceActivity(state, 7999999);  // VAD is handled before the clock.
    CHECK(poll(8000000) == Reason::None);
    state = ReplyStarted(state);
    state = ReplyFinished(state);  // Realtime also restarts, even without restarting audio.
    CHECK(poll(9000000) == Reason::None);
    CHECK(poll(17000000) == Reason::Silence);
    state = {};
    CHECK(poll(0) == Reason::None);
    CHECK(poll(7000000, true, false, false) == Reason::None);  // Popup playback.
    CHECK(poll(8000000) == Reason::None);
    CHECK(poll(15999999) == Reason::None);
    CHECK(poll(16000000) == Reason::Silence);
    state = VoiceChanged({}, 0, true, true, false);
    CHECK(state.voice_active);
    state = ReplyStarted(state);
    state = VoiceChanged(state, 1000000, false, false, true);
    CHECK(!state.voice_active);  // Realtime VAD end during playback must not be lost.
    state = ReplyFinished(state, true);
    CHECK(poll(2000000, true, state.voice_active) == Reason::None);
    CHECK(poll(10000000, true, state.voice_active) == Reason::Silence);
    state = ReplyStarted({});
    state = VoiceChanged(state, 0, true, false, true);
    state = ReplyFinished(state, true);
    CHECK(state.voice_active);  // A sentence spanning playback end is still speech.
    CHECK(poll(20000000, true, state.voice_active) == Reason::None);
    state = VoiceChanged(state, 21000000, false, true, false);
    CHECK(poll(30000000, true, state.voice_active) == Reason::None);
    CHECK(poll(81000000, true, state.voice_active) == Reason::ResponseTimeout);
    state = VoiceChanged({}, 0, true, false, false);
    CHECK(!state.voice_active && state.response_since == -1);  // Ignore VAD outside a conversation.
    state = VoiceChanged({}, 0, true, true, false);
    state = ReplyFinished(ReplyStarted(state));
    CHECK(!state.voice_active);  // Auto-mode restarts the audio engine with no stale VAD.
    state = VoiceActivity({}, 0);
    CHECK(poll(59000000) == Reason::None);
    state = {};  // A new explicit wake starts a fresh conversation.
    CHECK(poll(59000000) == Reason::None);
    CHECK(poll(66999999) == Reason::None);
    CHECK(poll(67000000) == Reason::Silence);
    state = VoiceChanged({}, 0, true, true, false);
    state = Restart(state, true);  // Wake again without stopping continuous capture.
    CHECK(state.voice_active);
    CHECK(poll(9000000, true, state.voice_active) == Reason::None);
    state = Restart(state, false);  // A newly started engine cannot inherit stale VAD.
    CHECK(!state.voice_active);
    CHECK(poll(10000000, true, state.voice_active) == Reason::None);
    CHECK(poll(18000000, true, state.voice_active) == Reason::Silence);
    std::printf("Conversation timeout: %u checks passed\n", checks);
}
