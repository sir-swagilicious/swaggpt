"""
Utility module for running async code from synchronous Flask routes.
Provides a single persistent event loop shared across the entire application.
"""
import asyncio
import threading

# Global event loop for the entire application
_loop = None
_loop_lock = threading.Lock()
_thread = None

def get_event_loop():
    """Get or create the global persistent event loop"""
    global _loop, _thread
    
    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            # Run the loop in a background thread so it stays alive
            _thread = threading.Thread(target=_loop.run_forever, daemon=True)
            _thread.start()
        return _loop

def run_async(coro):
    """
    Run an async coroutine from synchronous code.
    Uses the global persistent event loop.
    Returns the actual result, not a coroutine.
    """
    loop = get_event_loop()
    
    # Run the coroutine in the persistent loop and wait for result
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=120)  # 2 minute timeout