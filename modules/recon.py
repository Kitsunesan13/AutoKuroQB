import os
from .utils import run_os_command

def execute_streamed_recon(domain, output_dir, pipeline_cmd):
    """
    OPTIMIZED: Uses Unix Pipes (Subfinder -> Httpx)
    """
    live_file = os.path.join(output_dir, "live_hosts.txt")
    
    # Split pipeline command to inject domain and output args
    parts = pipeline_cmd.split("|", 1)
    if len(parts) < 2: return None # Fallback logic needed if config invalid

    subfinder_part = f"{parts[0]} -d {domain}"
    httpx_part = f"{parts[1]} -o {live_file}"
    
    full_cmd = f"{subfinder_part} | {httpx_part}"
    
    run_os_command(full_cmd, "Streamed Recon")
    
    if os.path.exists(live_file) and os.path.getsize(live_file) > 0:
        return live_file
    return None

def execute_naabu(input_file, output_dir, flags):
    output_file = os.path.join(output_dir, "open_ports.txt")
    cmd = f"naabu -list {input_file} {flags} -o {output_file}"
    run_os_command(cmd, "Naabu (Port Scan)")
    if os.path.exists(output_file) and os.path.getsize(output_file) > 0: return output_file
    return None