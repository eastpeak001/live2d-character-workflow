"""Read or replace main.xml in a Cubism 5 authoring document, in memory.

Container layout follows the MIT-licensed moc2cmo project. See THIRD_PARTY.md.
Texture and other resources retain their original stored byte streams.
"""
from dataclasses import dataclass
from io import BytesIO
from struct import pack, unpack_from
import zipfile
import zlib


@dataclass
class Member:
    path: str
    offset: int
    size: int
    slot: int
    compression: int


class Archive:
    def __init__(self, data):
        if data[:4] != b"CAFF" or len(data) < 60:
            raise ValueError("Expected an editable Cubism CAFF document.")
        self.data = data
        self.key = unpack_from(">I", data, 14)[0]
        high = 0xffffffff if self.key & 0x80000000 else self.key
        self.key64 = (high << 32) | self.key
        self.xor = bytes(x ^ (self.key & 255) for x in range(256))
        cursor = 58
        count = unpack_from(">I", data, 54)[0] ^ self.key
        if not 0 < count <= len(data) // 24:
            raise ValueError("Invalid resource count.")

        def string():
            nonlocal cursor
            size = 0
            for _ in range(4):
                byte = data[cursor] ^ (self.key & 255)
                cursor += 1
                size = (size << 7) | (byte & 127)
                if byte < 128:
                    break
            else:
                raise ValueError("Invalid resource name.")
            if size > len(data) - cursor:
                raise ValueError("Truncated resource name.")
            value = data[cursor:cursor+size].translate(self.xor).decode()
            cursor += size
            return value

        self.members = []
        for _ in range(count):
            name = string()
            string()
            offset, size = unpack_from(">QI", data, cursor)
            entry = Member(name, offset ^ self.key64, size ^ self.key, cursor, data[cursor+13] ^ (self.key & 255))
            cursor += 22
            if entry.offset + entry.size > len(data):
                raise ValueError("Truncated resource.")
            self.members.append(entry)
        if len({m.path for m in self.members}) != len(self.members):
            raise ValueError("Duplicate resource names.")
        self.table_end = cursor
        self.main = next(m for m in self.members if m.path == "main.xml")

    def xml(self):
        m = self.main
        stored = self.data[m.offset:m.offset+m.size].translate(self.xor)
        if m.compression == 16:
            return stored
        if m.compression != 33:
            raise ValueError("Unsupported main.xml compression.")
        try:
            archive = zipfile.ZipFile(BytesIO(stored))
        except zipfile.BadZipFile:
            if stored[:4] != b"PK\x03\x04" or stored[-16:-12] != b"PK\x07\x08":
                raise ValueError("Unrecognized streaming XML container.")
            name, extra = unpack_from("<HH", stored, 26)
            if stored[30:30+name] != b"contents":
                raise ValueError("Unknown XML entry.")
            crc, length, expected = unpack_from("<III", stored, len(stored)-12)
            start = 30 + name + extra
            decoded = zlib.decompress(stored[start:start+length], -15)
            if len(decoded) != expected or zlib.crc32(decoded) != crc:
                raise ValueError("Damaged XML stream.")
            return decoded
        with archive:
            return archive.read("contents")

    def with_xml(self, xml):
        raw = xml
        if self.main.compression == 33:
            out = BytesIO()
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("contents", xml)
            raw = out.getvalue()
        # Leave the preview and all other original resources at their exact offsets.
        # If the new XML grows, move it behind them and erase the obsolete XML bytes.
        output = bytearray(self.data)
        m = self.main
        if output[-2:] != b"bc":
            raise ValueError("Unsupported Cubism archive footer.")
        encoded = raw.translate(self.xor)
        output[m.offset:m.offset+m.size] = b"\x00" * m.size
        target = m.offset
        if len(encoded) > m.size:
            target = len(output)-2
            output[target:target] = encoded
        else:
            output[target:target+len(encoded)] = encoded
        output[m.slot:m.slot+12] = pack(">QI", target ^ self.key64, len(encoded) ^ self.key)
        return bytes(output)
