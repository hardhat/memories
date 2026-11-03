#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>

#ifndef __SDCC_VERSION_MAJOR
#define __at(addr)
#define __naked
#define __sfr
#define va_list struct {int dummy; }
#define va_start(ap, last)
#define va_end(ap)
#endif

#include <zos_sys.h>
#include <zos_video.h>
#include <zos_keyboard.h>
#include <zos_vfs.h>
#include <zvb.h>

#include "main.h"
#include "memo_vm.h"
#include "memo_dat.h"
#include "memo_host.h"
#include "Nicety.h"
#include "textaccel.h"

gfx_context ctx;

bool quit = false;

uint8_t sprite_count=0;
uint8_t last_sprite_count=0;
gfx_sprite sprites[128];

zos_dev_t ser;
uint16_t controller_state;

uint8_t text_tiles[256*20];

uint8_t *font = FONT_NICETY_BITMAP;

void debug_log(const char *message)
{
    size_t size=strlen(message);

    write(ser, message, &size);
    size=2;
    write(ser, "\r\n", &size);
}

void debug_logf(const char *format, ...)
{
    char buffer[256];
    va_list args;
    va_start(args, format);
    vsprintf(buffer, format, args);
    va_end(args);
    debug_log(buffer);
}

void reset_sprites(void)
{
    last_sprite_count = sprite_count;
    sprite_count=0;
    memset(sprites, 0, sizeof(sprites));
}

uint8_t add_sprite(uint16_t x, uint8_t y, uint8_t sprite)
{
    if(sprite_count >= 128) return -1;
    sprites[sprite_count].x = x+16; // Note sprites are displayed anchored the bottom right corner
    sprites[sprite_count].y = y+16;
    sprites[sprite_count].tile = sprite;
    sprites[sprite_count].flags = 0;
    return sprite_count++;
}

void render_sprites(void)
{
    uint8_t count = sprite_count;
    if(count < last_sprite_count) count = last_sprite_count;
    gfx_sprite_render_array(&ctx, 0, sprites, count);
}

void clear_sprites(void)
{
    reset_sprites();
    sprite_count=128;
    render_sprites();
    sprite_count=0;
}

void initialize_game()
{
    memo_vm_init();
    dat_open("memo.dat",0x4F4D454D); // 'MEMO'
    memo_host_initialize();
    gfx_initialize(ZVB_CTRL_VID_MODE_GFX_320_8BIT,&ctx);
    clear_text_buffer(0); // Clear the off-screen text buffer initially

    char line[80];
    memset(line, 0, sizeof(line));
    for(uint8_t i=0;i<15;i++) {
        draw_bg((const uint8_t *)line, 0, i, 80, 1); // Draw each line to the background
        draw_fg((const uint8_t *)line, 0, i, 80, 1); // Draw each line to the foreground
    }

    char buffer[60];
    for(uint8_t i=0;i<60;i++) buffer[i] = i+1; // Initialize buffer to sequence
    draw_bg((const uint8_t *)buffer, 0, 4, 20, 3); // Example usage of draw_bg with the buffer

    const char *text[] = {
        "     Memories of Ravenwood Academy",
        "     a tale of mystery",
        "     by hardhat",
        "     Copyright 2026",
        "     All rights reserved",
        "     1 2 3 4 5 6 7 8 9"
    };
    for(uint8_t i=0;i<6;i++) {
        if((i&1) == 0) clear_text_buffer(1);
        draw_text(0, ((i&1)<<3), text[i], i+10); // Draw initial text to the off-screen text buffer
        if((i&1) == 1) render_text_buffer(1+20*((i&7)>>1), 20); // Render the off-screen text buffer to the screen tileset
    }
}

void draw_bg(const uint8_t *data, uint8_t x, uint8_t y, uint8_t width, uint8_t height)
{
    for(uint8_t j=0;j<height;j++) {
        gfx_tilemap_load(&ctx, &data[j*width], width, 0, x, y+j);
    }
}

void draw_fg(const uint8_t *data, uint8_t x, uint8_t y, uint8_t width, uint8_t height)
{
    for(uint8_t j=0;j<height;j++) {
        gfx_tilemap_load(&ctx, &data[j*width], width, 1, x, y+j);
    }
}

void load_palette(const uint16_t *palette, uint8_t offset, uint8_t count)
{
    gfx_palette_load(&ctx, palette, offset, count);
}

void load_tileset(const uint8_t *tileset, uint16_t offset, uint16_t size, uint8_t palette_base)
{
    gfx_tileset_options options0 = {TILESET_COMP_NONE, offset, palette_base, 0};
    gfx_tileset_load(&ctx, tileset, size, &options0);
}

void clear_text_buffer(uint8_t color)
{
    memset(text_tiles, color, sizeof(text_tiles));
}

void draw_text_pixel(uint16_t x, uint8_t y,uint8_t color)
{
    //int offset = (x/16)*256+y*16+(x%16);
    uint16_t offset = ((x>>4)<<8)+(y<<4)+(x&0x0F);
    if(offset>=256*20) return;  // Clip
    text_tiles[offset] = color;
}

void draw_text_pixel_offset(uint16_t offset, uint8_t color)
{
    if(offset>=256*20) return;  // Clip
    text_tiles[offset] = color;
}

void draw_text_char(uint16_t x, uint8_t y, uint8_t c, uint8_t color)
{
    if(((x&15)>8) || ((y&15)>8)) {
        // Straddling tiles, draw pixel by pixel
        const uint8_t *ptr = font+((c-32)<<3);
        for(uint8_t i=0;i<8;i++)
        {
            uint8_t mask = 1<<(7-i);
            for(uint8_t j=0;j<8;j++)
            {
                if(ptr[j] & mask)
                    draw_text_pixel(x+i, y+j, color);
            }
        }
    } else {
        // Save some computation on the common case of aligned text by precomputing the offset and only checking tile bounds once.
        uint16_t offset = ((x>>4)<<8)+(y<<4)+(x&0x0F);
        const uint8_t *ptr = font+((c-32)<<3);
        draw_text_char_aligned(ptr, &text_tiles[offset], color);
    }
}

void draw_text(uint16_t x, uint8_t y, const char *text, uint8_t color)
{
    for(int i=0;i<strlen(text);i++)
    {
        uint8_t c = text[i];
        if(c<32 || c>127) c=32;
        draw_text_char(x+i*8, y, c, color);
    }
}

void draw_char_opaque(uint16_t x, uint8_t y, uint8_t c, uint8_t fg, uint8_t bg)
{
    if(c<32 || c>127) c=32;
    const uint8_t *ptr = font+((c-32)<<3);
    if(((x&15)<=8) && ((y&15)<=8)) {
        // use faster offset instead.
        uint16_t offset=((x>>4)<<8)+(y<<4)+(x&0x0F);
#if 0
        for(uint8_t j=0;j<8;j++) {
            uint8_t mask=0x80;
            uint8_t pat=ptr[j]; // get the pixel pattern
            for(uint8_t i=0;i<8;i++) {
                if(pat & mask)
                    draw_text_pixel_offset(offset, fg);
                else
                    draw_text_pixel_offset(offset, bg);
                offset++;
                mask>>=1;
            }
            offset+=8; // 8 to move to the next line
        }
#else
        draw_text_char_opaque_aligned(ptr, &text_tiles[offset], fg, bg);
#endif
        return;
    }
            
    for(uint8_t i=0;i<8;i++)
    {
        uint8_t mask = 1<<(7-i);
        for(uint8_t j=0;j<8;j++)
        {
            if(ptr[j] & mask)
                draw_text_pixel(x+i, y+j, fg);
            else
                draw_text_pixel(x+i, y+j, bg);
        }
    }
}

void draw_text_opaque(uint16_t x, uint8_t y, const char *text, uint8_t fg, uint8_t bg)
{
    for(int i=0;i<strlen(text);i++)
    {
        uint8_t c = text[i];
        draw_char_opaque(x, y, c, fg, bg);
        x+=8;
    }
}

void render_text_buffer(uint16_t first_tile, uint16_t num_tiles)
{
    gfx_tileset_options opts = {TILESET_COMP_NONE, first_tile<<8, 0, 0};
    gfx_tileset_load(&ctx, text_tiles, num_tiles<<8, &opts);
}

void send_input(uint8_t input, bool pressed)
{
    game_handle_input(input, pressed);
}

uint8_t handle_input(uint8_t key)
{
    switch(key)
    {
        case KB_ESC:
            quit = true;
            return MAX_INPUT;
        case KB_KEY_W:
        case KB_UP_ARROW:
        case KB_NUMPAD_8:
            return INPUT_UP;
        case KB_KEY_S:
        case KB_DOWN_ARROW:
        case KB_NUMPAD_2:
            return INPUT_DOWN;
        case KB_KEY_A:
        case KB_LEFT_ARROW:
        case KB_NUMPAD_4:
            return INPUT_LEFT;
        case KB_KEY_D:
        case KB_RIGHT_ARROW:
        case KB_NUMPAD_6:
            return INPUT_RIGHT;
        case KB_KEY_V:
        case KB_KEY_SPACE:
            return INPUT_A;
        case KB_KEY_BACKSPACE:
        case KB_KEY_B:
            return INPUT_B;
        case KB_KEY_COMMA:
        case KB_KEY_X:
            return INPUT_X;
        case KB_KEY_PERIOD:
        case KB_KEY_Y:
            return INPUT_Y;
        case KB_KEY_ENTER:
            return INPUT_START;
        case KB_KEY_QUOTE:
        case KB_RIGHT_SHIFT:
            return INPUT_SELECT;
        case KB_KEY_LEFT_BRACKET:
        case KB_KEY_Q:
            return INPUT_L;
        case KB_KEY_RIGHT_BRACKET:
        case KB_KEY_E:
            return INPUT_R;
        default:
            return MAX_INPUT;
    }
}

void process_input(void)
{
    unsigned char keys[32];
    int size;
    bool pressed = true;

    do {
        size=32;
        read(DEV_STDIN, &keys, &size);
        for(int i=0;i<size;i++) {
            char key = keys[i];
           //debug_logf("Processing input key %02x.", key);
           if(key == KB_RELEASED) {
                pressed = false;
                continue;
            } else {
                uint8_t input = handle_input(key);
                if(input >= MAX_INPUT) {
                    pressed = true;
                    continue;
                }
                send_input(input, pressed);
                pressed=true;
            }
        }
    } while(size>0);
}

int main(int argc, char *argv[])
{
    ser = open("#SER0",O_WRONLY);
    if (ser < 0) {
        printf("Failed to open serial port\n");
	    exit(1);
    }

    initialize_game();

    while(!quit)
    {
        process_input();

        gfx_wait_end_vblank(&ctx);
        game_update(16);
        gfx_wait_vblank(&ctx);
        render_sprites();
        game_draw();
    }

    debug_log("Quitting.");

    // Clear out sprites
    clear_sprites();
    zvb_sound_reset();
    ioctl(DEV_STDOUT, CMD_RESET_SCREEN, NULL);
    printf("Exiting...\n");

    printf("Goodbye!\n");
    close(ser);

    exit(0);
   return 0;
}