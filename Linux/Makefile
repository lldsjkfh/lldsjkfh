CC      ?= gcc
CFLAGS  ?= -Wall -Wextra -O2 -pthread
TARGET   = threadpool

$(TARGET): threadpool.c
	$(CC) $(CFLAGS) threadpool.c -o $(TARGET)

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(TARGET)

.PHONY: run clean
