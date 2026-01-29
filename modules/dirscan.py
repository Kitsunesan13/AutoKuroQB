import os
import json
import asyncio
from .utils import run_async_command
from rich.console import Console

console = Console()

def get_valid_wordlist(primary, fallback):
    if os.path.exists(primary): return primary
    elif os.path.exists(fallback): return fallback
    else: return None

def filter_priority_targets(input_file, output_dir, config_keywords):
    priority_file = os.path.join(output_dir, "priority_hosts_ferox.txt")
    keywords = config_keywords if config_keywords else ["admin", "login", "api", "dev"]
    priority_urls = set()
    total_hosts = 0
    try:
        with open(input_file, 'r', errors='ignore') as f:
            for line in f:
                total_hosts += 1
                url = line.strip()
                if any(k in url.lower() for k in keywords): priority_urls.add(url)
    except: return input_file
    
    if total_hosts <= 20: return input_file
    if not priority_urls:
        os.system(f"head -n 10 {input_file} > {priority_file}")
        return priority_file

    with open(priority_file, 'w') as f: f.write('\n'.join(priority_urls))
    return priority_file

async def execute_feroxbuster_async(input_file, output_dir, flags, wordlist_primary, wordlist_fallback, config_keywords, timeout=None):
    wordlist = get_valid_wordlist(wordlist_primary, wordlist_fallback)
    if not wordlist:
        console.print("[red][X] Error: No wordlist found.[/red]")
        return None

    target_file = filter_priority_targets(input_file, output_dir, config_keywords)
    json_output = os.path.join(output_dir, "ferox_raw.json")
    final_txt_output = os.path.join(output_dir, "hidden_dirs.txt")
    
    cmd = f"feroxbuster {flags} --stdin -w {wordlist} -o {json_output}"
    import shlex, subprocess
    try:
        args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *args, stdin=asyncio.subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        with open(target_file, 'rb') as f: stdin_data = f.read()
        try:
            await asyncio.wait_for(process.communicate(input=stdin_data), timeout=timeout)
        except asyncio.TimeoutError:
            try: process.kill()
            except: pass
    except Exception as e:
        console.print(f"[red]Ferox Error: {e}[/red]")

    urls = set()
    if os.path.exists(json_output):
        try:
            with open(json_output, 'r', errors='ignore') as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if "url" in data: urls.add(data["url"])
                    except: pass
        except: pass
    
    if urls:
        with open(final_txt_output, 'w') as f: f.write('\n'.join(urls))
        return final_txt_output
    return None