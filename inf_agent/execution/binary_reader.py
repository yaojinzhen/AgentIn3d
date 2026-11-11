"""Bounded reads from an embedded GLB BIN chunk."""

import struct

BINARY_READ_BYTES = 64 * 1024


class BinaryChunk:
    def __init__(self, stream, offset, length):
        self.stream, self.offset, self.length = stream, offset, length

    def __len__(self):
        return self.length

    def values(self, fmt, offset, stride, count):
        value = struct.Struct(fmt)
        if (
            offset < 0
            or count < 0
            or stride < value.size
            or (count and offset + (count - 1) * stride + value.size > self.length)
        ):
            raise ValueError("accessor read exceeds BIN bounds or has invalid stride")
        batch = max(1, (BINARY_READ_BYTES - value.size) // stride + 1)
        for first in range(0, count, batch):
            n = min(batch, count - first)
            size = (n - 1) * stride + value.size
            self.stream.seek(self.offset + offset + first * stride)
            payload = self.stream.read(size)
            if len(payload) != size:
                raise ValueError("GLB BIN accessor data is truncated")
            for i in range(n):
                yield value.unpack_from(payload, i * stride)
