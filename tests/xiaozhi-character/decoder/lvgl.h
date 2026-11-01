#ifndef HOST_LVGL_H
#define HOST_LVGL_H
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#define LV_USE_DRAW_SW_ASM 0
#define LV_DRAW_SW_ASM_HELIUM 1
#define LV_FS_MODE_RD 1
#define LV_FS_RES_OK 0
#define LV_FS_SEEK_SET 0
#define LV_FS_SEEK_CUR 1
typedef struct { void *unused; } lv_fs_file_t;
typedef int lv_fs_res_t;
void *lv_malloc(size_t n);
void *lv_realloc(void *p, size_t n);
void lv_free(void *p);
int lv_fs_open(lv_fs_file_t *f, const void *p, int m);
int lv_fs_read(lv_fs_file_t *f, void *p, size_t n, void *count);
int lv_fs_seek(lv_fs_file_t *f, size_t p, int mode);
int lv_fs_tell(lv_fs_file_t *f, uint32_t *p);
int lv_fs_close(lv_fs_file_t *f);
#endif
