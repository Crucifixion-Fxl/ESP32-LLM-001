# Historical experiments

These modules preserve earlier approaches for research and comparison. They are
not the recommended deployment pipeline.

- `train_qat_baseline.py`: early training variant targeting selected MLP layers.
- `train_qat_weights_only.py`: ternary weight training without the current
  firmware-aligned activation simulation.
- `compare_int4_offset.py`: earlier offset-based INT4 reconstruction, retained to
  explain the decoding investigation; it differs from firmware two's-complement decoding.

Run modules from the repository root (`python -m tools.experiments.<module>`).
Use a separate `ESP32_LLM_WORKSPACE` to avoid replacing production artifacts.
For current training, use [train_qat.py](../training/train_qat.py).
