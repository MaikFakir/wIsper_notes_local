import torch

def check_gpu_availability():
    """
    Checks if a CUDA-enabled GPU is available to PyTorch and prints the result.
    """
    print("--- Verificando disponibilidad de GPU con PyTorch ---")
    is_available = torch.cuda.is_available()
    print(f"¿Hay una GPU disponible (CUDA)? -> {is_available}")

    if is_available:
        gpu_count = torch.cuda.device_count()
        current_device = torch.cuda.current_device()
        device_name = torch.cuda.get_device_name(current_device)
        print(f"Número de GPUs encontradas: {gpu_count}")
        print(f"Dispositivo actual: {current_device}")
        print(f"Nombre del dispositivo: {device_name}")
    else:
        print("No se detectó ninguna GPU compatible con CUDA.")

    print("-------------------------------------------------")

if __name__ == "__main__":
    check_gpu_availability()