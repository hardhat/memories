ZOS_PATH ?= ../Zeal-8-bit-OS
ZVB_SDK_PATH ?= ../Zeal-VideoBoard-SDK
BIN=bin/memo.bin
OBJ=obj/dat_io_zos.rel obj/memo_dat.rel obj/memo_vm.rel obj/main.rel obj/host.rel obj/game.rel obj/screen.rel obj/portrait.rel obj/cg.rel obj/stream.rel obj/title.rel obj/textaccel.rel
IMG=img/tileset.zts
CC=sdcc
CFLAGS=-mz80 --std-c2x -c -I $(ZOS_PATH)/sdk/sdcc/include/ -I $(ZVB_SDK_PATH)/include -I script/build --codeseg TEXT --debug --opt-code-size
AS=sdasz80 -o -l -s
OBJCOPY=objcopy
LD=sdldz80
MAP=map/bg.ztm map/fg.ztm
LDFLAGS=-n -y -mjwx -i -b _HEADER=0x4000 -k $(ZOS_PATH)/sdk/sdcc/lib -l z80 $(ZOS_LDFLAGS)
ZOS_LIBS=-k $(ZVB_SDK_PATH)/lib -l zvb_sound -l zvb_gfx
# 1. Detect the operating system. Cygwin/MSYS/MinGW make also see OS=Windows_NT, but they run
# commands through a POSIX shell, so uname tells them apart from native cmd.exe make.
UNAME_S := $(shell uname -s 2>/dev/null)
ifneq ($(filter CYGWIN% MSYS% MINGW%,$(UNAME_S)),)
    POSIX_SHELL = 1
endif
ifeq ($(OS)$(POSIX_SHELL),Windows_NT)
    # Windows settings (cmd.exe native commands)
    # Note: 'RM' uses 'del /q /f' and 'rmdir /s /q' to mimic 'rm -rf'
    RM = del /q /f
    RMDIR = rmdir /s /q
    CP = copy /y
    MKDIR = mkdir
    FIX_PATH = $(subst /,\,$1)
    EXE_EXT = .exe
else
    # Linux / macOS / Cygwin / MSYS settings
    RM = rm -f
    RMDIR = rm -rf
    CP = cp
    MKDIR = mkdir -p
    FIX_PATH = $1
    EXE_EXT =
endif

all: init $(BIN)

PHONY: init clean reallyclean

init:
	-$(MKDIR) obj
	-$(MKDIR) bin

$(BIN): $(OBJ)
	$(LD) $(LDFLAGS) -o $(BIN:.bin=.ihx) \
	../Zeal-8-bit-OS/sdk/sdcc/bin/zos_crt0.rel $(OBJ) $(ZOS_LIBS)
	$(OBJCOPY) --input-target=ihex --output-target binary $(BIN:.bin=.ihx) $(BIN)
	-$(CP) $(call FIX_PATH,$(BIN)) s

obj/%.rel: engine/%.c
	$(CC) $(CFLAGS) -o $@ $<

obj/%.rel: engine/%.asm
	$(AS) $@ $<

#img/%.zts: img/%.gif
#	python3 $(ZVB_SDK_PATH)/tools/zeal2gif/gif2zeal.py -i $<
#	-$(CP) $(call FIX_PATH,$(IMG)) $(call FIX_PATH,bin/spookyst.zts)

#map/bg.ztm: map/street.tmx
#	python3 $(ZVB_SDK_PATH)/tools/tiled2zeal/tiled2zeal.py -i $< -o $@ -l 1
#map/fg.ztm: map/street.tmx
#	python3 $(ZVB_SDK_PATH)/tools/tiled2zeal/tiled2zeal.py -i $< -o $@ -l 2

obj/main.rel: engine/main.c engine/main.h engine/memo_vm.h engine/memo_dat.h engine/memo_host.h script/build/memo_ids.h engine/textaccel.h engine/Nicety.h engine/title.h
obj/host.rel: engine/host.c engine/memo_host.h engine/main.h engine/game.h engine/screen.h engine/portrait.h engine/cg.h engine/memo_dat.h engine/memo_vm.h script/build/memo_ids.h
obj/game.rel: engine/game.c engine/main.h engine/game.h engine/memo_host.h engine/memo_dat.h engine/memo_vm.h script/build/memo_ids.h
obj/screen.rel: engine/screen.c engine/screen.h engine/layout.h engine/main.h engine/memo_vm.h script/build/memo_ids.h
obj/portrait.rel: engine/portrait.c engine/portrait.h engine/stream.h engine/layout.h engine/main.h engine/memo_dat.h script/build/memo_ids.h
obj/cg.rel: engine/cg.c engine/cg.h engine/screen.h engine/stream.h engine/layout.h engine/main.h engine/memo_dat.h script/build/memo_ids.h
obj/stream.rel: engine/stream.c engine/stream.h engine/main.h engine/memo_dat.h script/build/memo_ids.h
obj/title.rel: engine/title.c engine/title.h engine/stream.h engine/layout.h engine/main.h engine/memo_dat.h script/build/memo_ids.h
obj/textaccel.rel: engine/textaccel.asm
obj/dat_io_zos.rel: engine/dat_io_zos.c engine/dat_io.h
obj/memo_dat.rel: engine/memo_dat.c engine/memo_dat.h engine/dat_io.h script/build/memo_ids.h
obj/memo_vm.rel: engine/memo_vm.c engine/memo_vm.h engine/memo_dat.h engine/memo_host.h script/build/memo_ids.h

# memo_ids.h and memo.dat are generated together by the script compiler; the engine checks
# memo.dat against the CRC in this header, so rebuild both whenever the script data or the
# compiler changes, and ship the new memo.dat with the new program.
PYTHON ?= python
SCRIPT_INPUTS=$(wildcard script/tools/memo_dat.py script/tools/memo/*.py script/common/*.json script/scenes/*.json script/assets/manifest.json)
script/build/memo_ids.h: $(SCRIPT_INPUTS)
	$(PYTHON) script/tools/memo_dat.py build

clean:
	-$(RM) $(call FIX_PATH,$(OBJ))
	-$(RM) $(call FIX_PATH,$(BIN))
	-$(RM) $(call FIX_PATH,obj/*.lst obj/*.sym obj/*.adb obj/*.asm)
	-$(RM) $(call FIX_PATH,bin/*.ihx bin/*.noi bin/*.map bin/*.cdb)

reallyclean: clean
	-$(RM) $(call FIX_PATH,img/*.zts img/*.ztp map/*.ztm bin/*.zts)
