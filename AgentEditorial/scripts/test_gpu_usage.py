"""Test script to verify GPU usage for embeddings and LLMs."""

import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_scripts.config.settings import settings
from python_scripts.utils.logging import setup_logging, get_logger
from python_scripts.vectorstore.embeddings_utils import (
    get_embedding_model,
    generate_embedding,
    generate_embeddings_batch,
)

setup_logging()
logger = get_logger(__name__)


def test_pytorch_cuda():
    """Test PyTorch CUDA availability."""
    print("\n" + "=" * 60)
    print("1. Testing PyTorch CUDA Availability")
    print("=" * 60)
    
    try:
        import torch
        
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"CUDA version: {torch.version.cuda}")
            print(f"Number of GPUs: {torch.cuda.device_count()}")
            print(f"Current GPU: {torch.cuda.current_device()}")
            print(f"GPU Name: {torch.cuda.get_device_name(0)}")
            print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        else:
            print("❌ CUDA is NOT available - GPU will not be used")
            return False
            
        return True
    except ImportError:
        print("❌ PyTorch is not installed")
        return False
    except Exception as e:
        print(f"❌ Error checking CUDA: {e}")
        return False


def test_embedding_model_device():
    """Test embedding model device placement."""
    print("\n" + "=" * 60)
    print("2. Testing Embedding Model Device")
    print("=" * 60)
    
    try:
        model = get_embedding_model()
        
        # Check device of the model
        if hasattr(model, 'device'):
            print(f"Model device attribute: {model.device}")
        
        # Check device of model parameters
        if hasattr(model, '_modules'):
            for name, module in model.named_modules():
                if hasattr(module, 'weight') and module.weight is not None:
                    if hasattr(module.weight, 'device'):
                        print(f"First parameter device ({name}): {module.weight.device}")
                        break
        
        # Try to get device from model's first parameter
        try:
            first_param = next(model.parameters())
            device = first_param.device
            print(f"Model parameters device: {device}")
            
            if 'cuda' in str(device):
                print("✅ Model is on GPU")
                return True
            else:
                print("❌ Model is on CPU")
                return False
        except Exception as e:
            print(f"⚠️  Could not determine device from parameters: {e}")
            return None
            
    except Exception as e:
        print(f"❌ Error loading embedding model: {e}")
        return False


def test_embedding_generation():
    """Test embedding generation and monitor GPU usage."""
    print("\n" + "=" * 60)
    print("3. Testing Embedding Generation")
    print("=" * 60)
    
    try:
        import torch
        
        # Clear GPU cache before test
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            initial_memory = torch.cuda.memory_allocated(0) / 1024**2
            print(f"Initial GPU memory allocated: {initial_memory:.2f} MB")
        
        # Generate single embedding
        print("\nGenerating single embedding...")
        start_time = time.time()
        embedding = generate_embedding("This is a test sentence for embedding generation.")
        elapsed = time.time() - start_time
        print(f"✅ Single embedding generated in {elapsed:.2f}s")
        print(f"   Embedding dimension: {len(embedding)}")
        
        if torch.cuda.is_available():
            memory_after_single = torch.cuda.memory_allocated(0) / 1024**2
            print(f"   GPU memory after single: {memory_after_single:.2f} MB")
            print(f"   Memory increase: {memory_after_single - initial_memory:.2f} MB")
        
        # Generate batch embeddings
        print("\nGenerating batch embeddings (10 texts)...")
        test_texts = [f"This is test text number {i} for batch embedding generation." for i in range(10)]
        start_time = time.time()
        embeddings = generate_embeddings_batch(test_texts, batch_size=5)
        elapsed = time.time() - start_time
        print(f"✅ Batch embeddings generated in {elapsed:.2f}s")
        print(f"   Number of embeddings: {len(embeddings)}")
        
        if torch.cuda.is_available():
            memory_after_batch = torch.cuda.memory_allocated(0) / 1024**2
            print(f"   GPU memory after batch: {memory_after_batch:.2f} MB")
            print(f"   Total memory increase: {memory_after_batch - initial_memory:.2f} MB")
            
            # Check GPU utilization
            if torch.cuda.is_available():
                print("\n📊 GPU Memory Summary:")
                print(f"   Allocated: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
                print(f"   Reserved: {torch.cuda.memory_reserved(0) / 1024**2:.2f} MB")
                print(f"   Max allocated: {torch.cuda.max_memory_allocated(0) / 1024**2:.2f} MB")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating embeddings: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ollama_gpu():
    """Test Ollama GPU usage."""
    print("\n" + "=" * 60)
    print("4. Testing Ollama GPU Usage")
    print("=" * 60)
    
    try:
        import requests
        
        ollama_url = settings.ollama_base_url or "http://localhost:11434"
        print(f"Ollama URL: {ollama_url}")
        
        # Check Ollama status
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print("✅ Ollama is running")
                models = response.json().get("models", [])
                print(f"   Available models: {len(models)}")
                for model in models[:5]:  # Show first 5
                    print(f"   - {model.get('name', 'unknown')}")
            else:
                print(f"⚠️  Ollama returned status {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to Ollama: {e}")
            print("   Make sure Ollama is running and accessible")
            return False
        
        # Check if Ollama is using GPU (this requires checking Docker container or Ollama logs)
        print("\n💡 To verify Ollama GPU usage:")
        print("   1. Check Docker container: docker exec editorial_ollama nvidia-smi")
        print("   2. Check Ollama logs: docker logs editorial_ollama | grep -i gpu")
        print("   3. Run a test inference and monitor: watch -n 1 nvidia-smi")
        
        return True
        
    except ImportError:
        print("⚠️  requests library not available")
        return False
    except Exception as e:
        print(f"❌ Error checking Ollama: {e}")
        return False


def main():
    """Run all GPU tests."""
    print("\n" + "=" * 60)
    print("GPU Usage Test Suite")
    print("=" * 60)
    
    results = {
        "pytorch_cuda": False,
        "embedding_device": None,
        "embedding_generation": False,
        "ollama": False,
    }
    
    # Test 1: PyTorch CUDA
    results["pytorch_cuda"] = test_pytorch_cuda()
    
    if not results["pytorch_cuda"]:
        print("\n❌ CUDA is not available. GPU tests cannot continue.")
        return
    
    # Test 2: Embedding model device
    results["embedding_device"] = test_embedding_model_device()
    
    # Test 3: Embedding generation
    results["embedding_generation"] = test_embedding_generation()
    
    # Test 4: Ollama
    results["ollama"] = test_ollama_gpu()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"PyTorch CUDA: {'✅' if results['pytorch_cuda'] else '❌'}")
    print(f"Embedding Model Device: {'✅ GPU' if results['embedding_device'] is True else '❌ CPU' if results['embedding_device'] is False else '⚠️  Unknown'}")
    print(f"Embedding Generation: {'✅' if results['embedding_generation'] else '❌'}")
    print(f"Ollama Connection: {'✅' if results['ollama'] else '❌'}")
    
    print("\n💡 Tips:")
    print("   - Run 'watch -n 1 nvidia-smi' in another terminal to monitor GPU usage")
    print("   - GPU utilization may spike during model loading and inference")
    print("   - Low utilization (1%) is normal when idle, should increase during processing")


if __name__ == "__main__":
    main()







