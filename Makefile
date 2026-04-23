CC      := gcc
CFLAGS  := -Wall -Wextra -O2 -std=c11
SRC     := src/main.c src/game.c src/render.c
OUT     := snake.exe

all: $(OUT)

$(OUT): $(SRC) src/game.h src/render.h
	$(CC) $(CFLAGS) $(SRC) -o $(OUT)

run: $(OUT)
	./$(OUT)

clean:
	-del /Q $(OUT) 2>NUL || rm -f $(OUT)

.PHONY: all run clean
