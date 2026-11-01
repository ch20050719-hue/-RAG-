# GIF decoder host verification

Run `./run-tests.ps1` from PowerShell. This compiles the application's unmodified `gifdec.c` with MSVC and only substitutes LVGL allocation/filesystem and ESP logging APIs. Filesystem APIs are deliberately unsupported; the firmware's memory asset decoding path is exercised.

The runner writes native executables, decoded frames and reports under the project `.local/tmp/avatar-decoder-tests/`, leaving the test source directory clean. Override ApplicationRoot, VsDevCmd or Python when running on another machine; Python requires Pillow.

Each asset is checked at 96×96. Idle has two frames (4000/150 ms); talking has four frames (160 ms each). Tests decode five complete infinite loops plus a rewind frame, and verify zero remaining allocations after close. `compare_frames.py` compares all five loops byte for byte against Pillow BGRA output.

Both `LV_GIF_CACHE_DECODE_DATA=0` and `=1` are tested. The installed LVGL defaults to zero (`src/lv_conf_internal.h`, no corresponding CONFIG define in built sdkconfig.h). Allocation peaks measured by the host test include decoder buffers and LZW table, excluding original compressed asset data, display buffers, allocator bookkeeping, and audio. The 64-bit host structure size differs slightly from ESP32's 32-bit structure size; use these figures as conservative decoder estimates, not measured device free heap.

The native decoder emits existing MSVC narrowing warnings because the host has 64-bit size_t. Decoder source is not changed.
