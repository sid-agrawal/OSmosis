import proc
import psutil
import subprocess
import json

def run_process(name):
    """
    Start a hello process in the background
    Prints stdout for up to 2 seconds after process start
    
    :return: The hello process
    """
    print(f'Starting process "{name}"')
    
    process = subprocess.Popen(
        f'./{name}',
        text=True)
    
    return process

def print_stats(process):
    process = psutil.Process(process.pid)
        
    # Retrieve general stats
    info = {
        'pid': process.pid,
        'name': process.name(),
        'status': process.status(),
        'cpu_percent': process.cpu_percent(interval=1.0),
        'memory_info': process.memory_info(),
        'create_time': process.create_time(),
        'exe': process.exe(),
        'cwd': process.cwd(),
        'open_files': process.open_files(),
        'connections': process.net_connections()
    }
    
    print(json.dumps(info, indent=4))
    
    # Retrieve memory maps
    memory_maps = process.memory_maps()
        
    # Print details of memory maps
    print("Memory maps:")
    print("-" * 40)
    for mmap in memory_maps:
        print(f"Path: {mmap.path}")
        # print(f"Address: {mmap.addr}")
        print(f"Size: {mmap.size} bytes")  # Resident size, size - swap
        print(f"RSS: {mmap.rss} bytes")  # Resident size, size - swap
        # print(f"Permissions: {mmap.perms}")
        print(f"Anonymous: {mmap.anonymous}")
        print("-" * 40)
    
def terminate_process(process):
    process.terminate()
    process.wait()

if __name__ == "__main__":
    hello = run_process("hello1")
    try:
        print_stats(hello)
    except Exception as e:
        print("Error printing stats for hello")
        print(e)
    terminate_process(hello)