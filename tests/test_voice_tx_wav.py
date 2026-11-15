"""Tests for generated Voice TX WAV headers (no radio hardware required)."""
import struct
import unittest

from cq_prerecorder import RADIOS, build_voice_tx_wav


def chunks(wav: bytes):
    assert wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    offset = 12
    while offset < len(wav):
        tag = wav[offset:offset + 4]
        size = struct.unpack_from("<I", wav, offset + 4)[0]
        yield tag, wav[offset + 8:offset + 8 + size]
        offset += 8 + size + size % 2


class VoiceTxWavTests(unittest.TestCase):
    def test_radio_profiles(self):
        self.assertEqual(
            {r.number: r.sample_rate for r in RADIOS},
            {"7300": 8000, "7610": 16000, "9700": 16000},
        )

    def test_pcm_header_and_metadata_for_all_radios(self):
        for radio in RADIOS:
            with self.subTest(radio=radio.number):
                pcm = b"\x01\x02" * 160
                wav = build_voice_tx_wav(pcm, "test", radio)
                self.assertEqual(struct.unpack_from("<I", wav, 4)[0], len(wav) - 8)
                data = dict(chunks(wav))
                self.assertEqual(
                    struct.unpack("<HHIIHH", data[b"fmt "]),
                    (1, 1, radio.sample_rate, radio.sample_rate * 2, 2, 16),
                )
                self.assertEqual(data[b"data"], pcm)
                self.assertIn(b"IC-" + radio.number.encode(), data[b"LIST"])
                self.assertIn(b"INAM", data[b"LIST"])
                if radio.number == "9700":
                    self.assertNotIn(b"ICRD", data[b"LIST"])
                    self.assertNotIn(b"ISFT", data[b"LIST"])
                else:
                    self.assertIn(b"ICRD", data[b"LIST"])
                    self.assertIn(b"ISFT", data[b"LIST"])


if __name__ == "__main__":
    unittest.main()
