import torch

print("PyTorch version:", torch.__version__)
print("Is CUDA available:", torch.cuda.is_available())

if torch.cuda.is_available():
    print("Current CUDA device:", torch.cuda.current_device())
    print("CUDA device name:", torch.cuda.get_device_name(torch.cuda.current_device()))
else:
    print("CUDA is not available, using CPU.")
