"""Fixed UTF-8 byte tokenizer: no vocabulary downloads or unknown tokens."""


class ByteTokenizer:
    bos = 256
    eos = 257
    vocab_size = 258
    name = "aice-utf8-byte-v1"

    def encode(self, text, *, bos=True, eos=False):
        return ([self.bos] if bos else []) + list(text.encode("utf-8")) + ([self.eos] if eos else [])

    def decode(self, ids):
        values = [int(i) for i in ids]
        if any(i < 0 or i >= self.vocab_size for i in values):
            raise ValueError("token outside byte vocabulary")
        return bytes(i for i in values if i < 256).decode("utf-8", errors="replace")
