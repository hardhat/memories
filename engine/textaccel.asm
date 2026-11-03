	.module img
	.optsdcc -mz80

	.area _TEXT

     .globl _draw_text_char_aligned
     .globl _draw_text_char_opaque_aligned

_draw_text_char_aligned::

;void draw_text_char_aligned(const uint8_t *charpattern, uint8_t *target, uint8_t color)
    ; for(uint8_t j=0;j<8;j++)
    ; {
    ;    uint8_t mask=0x80;
    ;    uint8_t pat=charpattern[j]; // get the pixel pattern
    ;    for(uint8_t i=0;i<8;i++)
    ;    {
    ;        if(pat & mask)
    ;            *target=color;
    ;        target++;
    ;        mask>>=1;
    ;    }
    ;    target+=8; // 8 to move to the next line
    ; }

    ; HL is charpattern, DE is target, and color is the next byte on the stack.
    push ix
    ld ix,#0
    add ix,sp
    ld c,4(ix)

    ex de,hl
    ld b,#8
_dtca_outer_loop$:
    push bc
    ld a,(de)
    ld b,#8
_dtca_inner_loop$:
    rlca
    jr nc,_dtca_next$
    ld (hl),c
_dtca_next$:
    inc hl
    djnz _dtca_inner_loop$
    push de
    ld de,#8
    add hl,de
    pop de
    inc de
    pop bc
    djnz _dtca_outer_loop$
    pop ix
    pop hl
    inc sp
    jp (hl)
    ; push hl
    ; ret


_draw_text_char_opaque_aligned::

;void draw_text_char_opaque_aligned(const uint8_t *charpattern, uint8_t *target, uint8_t fg, uint8_t bg)
    ; for(uint8_t j=0;j<8;j++)
    ; {
    ;    uint8_t mask=0x80;
    ;    uint8_t pat=charpattern[j]; // get the pixel pattern
    ;    for(uint8_t i=0;i<8;i++)
    ;    {
    ;        if(pat & mask)
    ;            *target=fg;
    ;        else
    ;            *target=bg;
    ;        target++;
    ;        mask>>=1;
    ;    }
    ;    target+=8; // 8 to move to the next line
    ; }

    ; HL is charpattern, DE is target, and color is the next byte on the stack.
    push ix
    ld ix,#0
    add ix,sp
    ld a,4(ix)
    ld (_dtcoa_next$-1),A ; self-modifying code 
    ld c,5(ix)

    ex de,hl
    ld b,#8
_dtcoa_outer_loop$:
    push bc
    ld a,(de)
    ld b,#8
_dtcoa_inner_loop$:
    rlca
    ld (hl),c
    jr nc,_dtcoa_next$
    ld (hl),#0 ; This value gets filled in at the beginning of the function
_dtcoa_next$:
    inc hl
    djnz _dtcoa_inner_loop$
    push de
    ld de,#8
    add hl,de
    pop de
    inc de
    pop bc
    djnz _dtcoa_outer_loop$
    pop ix
    pop hl
    pop de  ; clear fg, bg from stack
    jp (hl)
    ; push hl
    ; ret
