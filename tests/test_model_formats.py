"""Small synthetic fixtures; no model download, GPU, training or attached board."""
import struct
import tempfile
from pathlib import Path
import unittest

import torch
from tools.export.quantize_embeddings import pack_tensor_to_int4
from tools.export.pack_weights import pack_single_bin
from tools.validation.validate_int4 import unpack_4bit_emb_firmware, unpack_158bit
from tools.training.train_qat import firmware_fake_quant_x


class ModelFormatTests(unittest.TestCase):
    def test_int4_signed_nibbles_match_firmware_order(self):
        packed = torch.tensor([[0xF8, 0x70]], dtype=torch.uint8)
        decoded = unpack_4bit_emb_firmware(packed, torch.ones((1, 1)))
        torch.testing.assert_close(decoded, torch.tensor([[-8., -1., 0., 7.]], dtype=torch.float16))

    def test_int4_quantize_round_trip_is_bounded_by_half_scale(self):
        weights = torch.tensor([[-1., -0.4, 0., 1.], [0., 0., 0., 0.]])
        packed, scales = pack_tensor_to_int4(weights)
        decoded = unpack_4bit_emb_firmware(packed, scales).float()
        self.assertTrue(torch.all((decoded - weights).abs() <= scales.float() / 2 + 0.001))
        self.assertTrue(torch.isfinite(decoded).all())

    def test_ternary_codes_keep_low_to_high_lane_order(self):
        packed = torch.tensor([[0b00100100]], dtype=torch.uint8)
        decoded = unpack_158bit(packed, torch.tensor(2.))
        torch.testing.assert_close(decoded, torch.tensor([[0., 2., -2., 0.]], dtype=torch.float16))

    def test_model_header_offsets_and_alignment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.bin'
            pack_single_bin({'a': torch.tensor([1., 2.]), 'b': torch.tensor([3, 4, 5], dtype=torch.uint8)}, path)
            data = path.read_bytes()
            magic, count, entries_size, names_size, weights_size = struct.unpack_from('<4sIIII', data)
            self.assertEqual((magic, count, entries_size), (b'MODL', 2, 64))
            pool = (20 + entries_size + names_size + 3) & ~3
            self.assertEqual(len(data), pool + weights_size)
            first = struct.unpack_from('<IHHII4I', data, 20)
            second = struct.unpack_from('<IHHII4I', data, 52)
            self.assertEqual(first[2:5], (0, 0, 4))
            self.assertEqual(second[2:5], (1, 4, 3))
            self.assertEqual(data[pool:pool+4], struct.pack('<2e', 1., 2.))
            self.assertEqual(data[pool+4:], bytes([3, 4, 5]))

    def test_activation_fake_quant_handles_zero_vectors(self):
        values = torch.zeros((2, 8), requires_grad=True)
        result = firmware_fake_quant_x(values)
        self.assertTrue(torch.isfinite(result).all())
        self.assertEqual(torch.count_nonzero(result).item(), 0)
        result.sum().backward()
        self.assertTrue(torch.isfinite(values.grad).all())


if __name__ == '__main__':
    unittest.main()
