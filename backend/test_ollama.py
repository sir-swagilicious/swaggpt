#!/usr/bin/env python3
"""
Test script to diagnose Ollama connection issues
"""
import requests
import json
import sys

OLLAMA_API_URL = "http://localhost:11434/api"

def test_ollama_connection():
    """Test basic connection to Ollama"""
    print("🔍 Testing Ollama Connection...")
    print(f"   URL: {OLLAMA_API_URL}")
    
    try:
        response = requests.get(f"{OLLAMA_API_URL}/tags", timeout=5)
        print(f"✅ Ollama is reachable (Status: {response.status_code})")
        
        data = response.json()
        if 'models' in data:
            print(f"📋 Available models: {len(data['models'])}")
            for model in data['models']:
                print(f"   - {model.get('name', 'unknown')}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Ollama. Is it running?")
        print("   Try: ollama serve")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_model_generation():
    """Test actual text generation with the model"""
    print("\n🔍 Testing Model Generation...")
    print("   Model: llama3.1b")
    print("   Prompt: 'Hello, how are you?'")
    
    payload = {
        "model": "llama3.1b",
        "prompt": "Hello, how are you?",
        "stream": False
    }
    
    try:
        print("   Sending request...")
        response = requests.post(
            f"{OLLAMA_API_URL}/generate",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Generation successful!")
            print(f"   Response: {data.get('response', 'No response')[:100]}...")
            print(f"   Tokens: {data.get('eval_count', 'unknown')}")
            print(f"   Duration: {data.get('total_duration', 0) / 1e9:.2f} seconds")
            return True
        else:
            print(f"❌ Generation failed (Status: {response.status_code})")
            print(f"   Error: {response.text}")
            return False
    except requests.exceptions.Timeout:
        print("❌ Request timed out after 30 seconds")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_streaming():
    """Test streaming response"""
    print("\n🔍 Testing Streaming Generation...")
    
    payload = {
        "model": "llama3.1b",
        "prompt": "Say 'streaming test successful'",
        "stream": True
    }
    
    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/generate",
            json=payload,
            stream=True,
            timeout=10
        )
        
        if response.status_code == 200:
            print("✅ Streaming connection established")
            full_response = ""
            
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if 'response' in data:
                            full_response += data['response']
                            print(f"   Chunk: {data['response']}", end='', flush=True)
                    except json.JSONDecodeError:
                        continue
            
            print(f"\n   Full response: {full_response}")
            return True
        else:
            print(f"❌ Streaming failed (Status: {response.status_code})")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_ollama_process():
    """Check if Ollama process is running"""
    import subprocess
    import platform
    
    print("\n🔍 Checking Ollama Process...")
    
    try:
        if platform.system() == "Linux":
            result = subprocess.run(['pgrep', '-f', 'ollama'], 
                                  capture_output=True, text=True)
            if result.stdout.strip():
                print(f"✅ Ollama process found (PID: {result.stdout.strip()})")
                
                # Check GPU usage
                try:
                    nvidia_result = subprocess.run(['nvidia-smi'], 
                                                  capture_output=True, text=True, timeout=5)
                    if 'ollama' in nvidia_result.stdout.lower():
                        print("✅ Ollama detected in GPU memory")
                    else:
                        print("⚠️  Ollama process found but not in GPU memory")
                except:
                    print("ℹ️  nvidia-smi not available")
            else:
                print("❌ No Ollama process found")
        elif platform.system() == "Windows":
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ollama.exe'], 
                                  capture_output=True, text=True)
            if 'ollama.exe' in result.stdout:
                print("✅ Ollama process found")
            else:
                print("❌ No Ollama process found")
                
        return True
    except Exception as e:
        print(f"❌ Error checking process: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🦙 Llama Connection Diagnostic Tool")
    print("=" * 50)
    
    # Run all tests
    connection_ok = test_ollama_connection()
    check_ollama_process()
    
    if connection_ok:
        test_model_generation()
        test_streaming()
    
    print("\n" + "=" * 50)
    print("💡 Troubleshooting Tips:")
    print("1. Ensure Ollama is running: ollama serve")
    print("2. Check if model is pulled: ollama pull llama3.1b")
    print("3. Check port availability: lsof -i :11434")
    print("4. Check Ollama logs for errors")
    print("=" * 50)