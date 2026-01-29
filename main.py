import typer
import yaml
import os
import sys
import asyncio
import functools
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    TaskProgressColumn
)
from modules import recon, crawler, scanner, dirscan, notify, utils, aggregator, context

app = typer.Typer()
console = Console()

def load_config():
    try:
        with open("config/config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        console.print("[bold red]❌ Config file not found![/bold red]")
        sys.exit(1)

CONFIG = load_config()

def get_dir_size(path):
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
        return f"{total_size / (1024 * 1024):.2f} MB"
    except:
        return "0.00 MB"

def run_async(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    verify: bool = typer.Option(False, "--verify", help="Check system dependencies and exit")
):
    if verify:
        utils.check_dependencies()
        raise typer.Exit()
    
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()

def check_findings_and_notify(step_name, file_path, target, should_notify):
    if file_path and os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        with open(file_path, 'r', errors='ignore') as f: count = sum(1 for _ in f)
        console.print(f"[bold red]   [!] ALERT: {count} findings in {step_name}![/bold red]")
        if should_notify:
            msg = f"🚨 *AutoKuro Alert* 🚨\n\n🎯 Target: `{target}`\n🛠 Stage: *{step_name}*\n⚠️ Findings: `{count}`\n📄 File: `{os.path.basename(file_path)}`"
            notify.send_telegram(msg, CONFIG['telegram'])

@app.command()
@run_async
async def start(
    domain: str = typer.Option(..., "-d", "--domain", help="Target Domain"),
    output: str = typer.Option("results", "-o", "--output", help="Output Directory"),
    mode: str = typer.Option("ranger", "-m", "--mode", help="Ghost, Ranger, Blitz"),
    profile: str = typer.Option("desktop", "-hw", "--hardware", help="mobile, desktop, vps"),
    cookie: str = typer.Option(None, "-c", "--cookie", help="Session Cookie"),
    proxy: str = typer.Option(None, "-p", "--proxy", help="Proxy URL"),
    notify_me: bool = typer.Option(False, "-n", "--notify", help="Enable Notifications")
):
    
    utils.check_dependencies()

    if mode not in CONFIG['modes']:
        console.print(f"[bold red]❌ Mode '{mode}' unknown![/bold red]")
        sys.exit(1)
    if profile not in CONFIG['hardware']:
        console.print(f"[bold red]❌ Profile '{profile}' unknown![/bold red]")
        sys.exit(1)
    
    GLOBAL_TIMEOUT = CONFIG.get('timeout', 600)
    adaptive_mode = CONFIG.get('adaptive_retry', True)

    base_config = CONFIG['modes'][mode]
    hw_multiplier = CONFIG['hardware'][profile]['multiplier']
    max_parallel = CONFIG['hardware'][profile].get('max_parallel_tasks', 4)
    SELECTED_CONFIG = utils.apply_hardware_profile(base_config, hw_multiplier)

    real_httpx_bin = utils.get_httpx_binary()
    if real_httpx_bin and real_httpx_bin != "httpx-toolkit":
        if "recon_stream" in SELECTED_CONFIG:
            SELECTED_CONFIG['recon_stream'] = SELECTED_CONFIG['recon_stream'].replace("httpx-toolkit", real_httpx_bin)

    if proxy:
        console.print(f"[bold yellow]🕵️ Proxy Enabled: {proxy}[/bold yellow]")
        httpx_bin_name = real_httpx_bin if real_httpx_bin else "httpx-toolkit"
        if httpx_bin_name in SELECTED_CONFIG['recon_stream']:
            SELECTED_CONFIG['recon_stream'] = SELECTED_CONFIG['recon_stream'].replace(httpx_bin_name, f"{httpx_bin_name} -http-proxy {proxy}")
        proxy_nuclei = f" -proxy {proxy}"
        for k in SELECTED_CONFIG:
            if "nuclei" in k and isinstance(SELECTED_CONFIG[k], str):
                SELECTED_CONFIG[k] += proxy_nuclei
        SELECTED_CONFIG['katana'] += f" -proxy {proxy}"
        SELECTED_CONFIG['feroxbuster'] += f" --proxy {proxy}"
        SELECTED_CONFIG['dalfox'] += f" --proxy {proxy}"

    if cookie:
        console.print(f"[bold green]🍪 Auth Mode: ON[/bold green]")
        cookie_header = f" -H 'Cookie: {cookie}'"
        for k in SELECTED_CONFIG:
             if "nuclei" in k and isinstance(SELECTED_CONFIG[k], str):
                SELECTED_CONFIG[k] += cookie_header
        SELECTED_CONFIG['katana'] += cookie_header
        SELECTED_CONFIG['feroxbuster'] += cookie_header
        SELECTED_CONFIG['gau'] += f" --cookie '{cookie}'"

    console.print(Panel(
        f"[bold green]Target:[/bold green] {domain}\n"
        f"[bold blue]Mode:[/bold blue]   {mode.upper()}\n"
        f"[bold cyan]Profile:[/bold cyan] {profile.upper()} ({hw_multiplier}x)\n"
        f"[bold yellow]Proxy:[/bold yellow]  {'ON' if proxy else 'OFF'}\n"
        f"[bold magenta]Notify:[/bold magenta] {'ON' if notify_me else 'OFF'}",
        title="🏴 [bold white]AutoKuro QB[/bold white] 🦊",
        border_style="red",
        subtitle="[dim] 戦術偵察 [/dim]",
        padding=(1, 15),
        expand=False 
    ))
    
    if os.path.exists("/dev/shm") and "results" in output:
        console.print("[dim]💡 Tip: Use [bold]/dev/shm[/bold] for RAMDisk speed.[/dim]\n")

    if notify_me:
        notify.send_telegram(f"🚀 *Scan Started* on `{domain}` | Mode: `{mode}` | HW: `{profile}`", CONFIG['telegram'])

    date_str = datetime.now().strftime("%Y-%m-%d") 
    target_dir = os.path.join(output, domain, date_str)
    os.makedirs(target_dir, exist_ok=True)
    
    total_steps = 12
    
    with Progress(
        SpinnerColumn(style="bold red"),
        TextColumn("[bold blue]{task.description}", justify="left"),
        BarColumn(bar_width=None, complete_style="green", finished_style="green"),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TextColumn("💾 {task.fields[data_size]}"),
        expand=True
    ) as progress:
        
        main_task = progress.add_task("[bold white]Running Pipeline...", total=total_steps, data_size="0.00 MB")

        def update_ui(desc, advance=1):
            size = get_dir_size(target_dir)
            progress.update(main_task, description=desc, data_size=size)
            if advance: progress.advance(main_task, advance)

        progress.update(main_task, description="[1/12] Streamed Recon (Pipe)...")
        expected_live = os.path.join(target_dir, "live_hosts.txt")
        if os.path.exists(expected_live) and os.path.getsize(expected_live) > 0:
            console.print(f"[dim]   ⏩ Checkpoint: Skipping Recon Stream[/dim]")
            live_file = expected_live
        else:
            live_file = await asyncio.to_thread(recon.execute_streamed_recon, domain, target_dir, SELECTED_CONFIG['recon_stream'], GLOBAL_TIMEOUT)
        
        update_ui("[1/12] Recon Done")
        
        if not live_file or not os.path.exists(live_file) or os.path.getsize(live_file) == 0: 
            console.print("[bold red]⛔ FATAL: No live hosts found. Scan aborted.[/bold red]")
            if notify_me: notify.send_telegram(f"❌ *Scan Failed*: No live hosts found for {domain}.", CONFIG['telegram'])
            raise typer.Exit()

        progress.update(main_task, description="[2-5/12] Parallel Discovery (Tech, Ports, Cloud, Takeover)...")
        
        sem = asyncio.Semaphore(max_parallel)
        
        async def run_safe_async(func, *args):
            async with sem: 
                return await func(*args)

        task_tech = run_safe_async(scanner.execute_nuclei_tech_detect, live_file, target_dir, SELECTED_CONFIG['nuclei_tech'], GLOBAL_TIMEOUT)
        task_cloud = run_safe_async(scanner.execute_nuclei_cloud, live_file, target_dir, SELECTED_CONFIG['nuclei_cloud'], GLOBAL_TIMEOUT)
        task_takeover = run_safe_async(scanner.execute_nuclei_takeover, live_file, target_dir, SELECTED_CONFIG['nuclei_takeover'], GLOBAL_TIMEOUT)
        
        expected_ports = os.path.join(target_dir, "open_ports.txt")
        if os.path.exists(expected_ports) and os.path.getsize(expected_ports) > 0:
             task_ports = asyncio.sleep(0.1) 
             console.print(f"[dim]   ⏩ Checkpoint: Skipping Naabu[/dim]")
        else:
             task_ports = run_safe_async(recon.execute_naabu_async, live_file, target_dir, SELECTED_CONFIG.get('naabu', '-silent'), GLOBAL_TIMEOUT)

        await asyncio.gather(task_tech, task_ports, task_takeover, task_cloud)

        check_findings_and_notify("Subdomain Takeover", os.path.join(target_dir, "takeover_results.txt"), domain, notify_me)
        check_findings_and_notify("Cloud Assets", os.path.join(target_dir, "cloud_enum_results.txt"), domain, notify_me)
        
        progress.advance(main_task, 3) 

        tech_file = os.path.join(target_dir, "technology.txt")
        extra_tags = context.analyze_tech_stack(tech_file, CONFIG.get('context_rules', {}))
        nuclei_context_flags = SELECTED_CONFIG['nuclei']
        if extra_tags:
            nuclei_context_flags += f" -tags {extra_tags}"

        progress.update(main_task, description="[6-7/12] Deep Scan (Dirbust, Crawl)...")
        
        task_ferox = run_safe_async(dirscan.execute_feroxbuster_async, live_file, target_dir, SELECTED_CONFIG['feroxbuster'], CONFIG['wordlist_path'], CONFIG['wordlist_fallback'], CONFIG.get('priority_keywords'), GLOBAL_TIMEOUT)
        task_gau = run_safe_async(crawler.execute_gau, domain, target_dir, SELECTED_CONFIG['gau'], GLOBAL_TIMEOUT)
        task_katana = run_safe_async(crawler.execute_katana, live_file, target_dir, SELECTED_CONFIG['katana'], GLOBAL_TIMEOUT)
        
        await asyncio.gather(task_ferox, task_gau, task_katana)
        
        crawler.merge_crawl_results(target_dir)
        all_urls_clean = os.path.join(target_dir, "all_urls_clean.txt")
        progress.advance(main_task, 2)

        progress.update(main_task, description="[8-9/12] Mining & JS Analysis...")
        
        task_param = run_safe_async(crawler.execute_paramspider, domain, target_dir, SELECTED_CONFIG['paramspider'], GLOBAL_TIMEOUT)
        
        js_file = os.path.join(target_dir, "js_files.txt")
        os.system(f"grep '.js' {all_urls_clean} > {js_file}")
        if os.path.exists(js_file) and os.path.getsize(js_file) > 0:
            task_js = run_safe_async(scanner.execute_nuclei, js_file, target_dir, SELECTED_CONFIG['nuclei_tokens'], "_secrets", GLOBAL_TIMEOUT)
        else:
            task_js = asyncio.sleep(0.1)

        await asyncio.gather(task_param, task_js)
        check_findings_and_notify("JS Secrets", os.path.join(target_dir, "nuclei_report_secrets.txt"), domain, notify_me)
        progress.advance(main_task, 2)

        progress.update(main_task, description="[10/12] Smart Nuclei Scanning...")
        expected_nuclei = os.path.join(target_dir, "nuclei_report.txt")
        
        if os.path.exists(expected_nuclei):
            console.print(f"[dim]   ⏩ Checkpoint: Skipping Nuclei[/dim]")
            nuclei_vuln = expected_nuclei
            update_ui("[10/12] Nuclei Done")
        else:
            target_groups = context.group_targets_smartly(live_file, target_dir)
            scan_tasks = []
            
            if os.path.exists(target_groups['api']):
                api_flags = SELECTED_CONFIG['nuclei'] + " -tags api,token,swagger,graphql"
                scan_tasks.append(run_safe_async(scanner.execute_nuclei, target_groups['api'], target_dir, api_flags, "_api", GLOBAL_TIMEOUT))
            
            if os.path.exists(target_groups['static']):
                static_flags = "-t http/takeovers -t http/misconfiguration -silent"
                scan_tasks.append(run_safe_async(scanner.execute_nuclei, target_groups['static'], target_dir, static_flags, "_static", GLOBAL_TIMEOUT))

            if os.path.exists(target_groups['dynamic']):
                dynamic_flags = SELECTED_CONFIG['nuclei'] + nuclei_context_flags
                scan_tasks.append(run_safe_async(scanner.execute_nuclei, target_groups['dynamic'], target_dir, dynamic_flags, "_dynamic", GLOBAL_TIMEOUT))

            if scan_tasks:
                await asyncio.gather(*scan_tasks)
            
            reports = [
                os.path.join(target_dir, "nuclei_report_api.txt"),
                os.path.join(target_dir, "nuclei_report_static.txt"),
                os.path.join(target_dir, "nuclei_report_dynamic.txt")
            ]
            final_report_content = set()
            for r in reports:
                if os.path.exists(r):
                    with open(r, 'r', errors='ignore') as f:
                        final_report_content.update(f.readlines())
            
            with open(expected_nuclei, 'w') as f:
                f.writelines(final_report_content)

            check_findings_and_notify("Nuclei Vulns", expected_nuclei, domain, notify_me)
            update_ui("[10/12] Nuclei Done")

        progress.update(main_task, description="[11-12/12] Finalizing (XSS & Secrets)...")
        
        params_file = os.path.join(target_dir, "parameters.txt")
        target_xss = params_file if (os.path.exists(params_file)) else all_urls_clean
        
        task_dalfox = run_safe_async(scanner.execute_dalfox, target_xss, target_dir, SELECTED_CONFIG['dalfox'], GLOBAL_TIMEOUT)
        task_truffle = run_safe_async(scanner.execute_trufflehog, target_dir, SELECTED_CONFIG['trufflehog'], GLOBAL_TIMEOUT)
        
        await asyncio.gather(task_dalfox, task_truffle)
        
        check_findings_and_notify("XSS Findings", os.path.join(target_dir, "dalfox_xss.txt"), domain, notify_me)
        check_findings_and_notify("Trufflehog Secrets", os.path.join(target_dir, "secrets_leak.txt"), domain, notify_me)
        
        json_path = aggregator.generate_json_report(domain, target_dir)
        update_ui("[12/12] Finished", advance=2)

    console.print("\n[bold green]✅ MISSION COMPLETE![/bold green]")
    console.print(f"[cyan]📊 JSON Report Generated:[/cyan] {json_path}")
    if notify_me: notify.send_telegram(f"✅ *Scan Finished* for `{domain}`. JSON Report Ready.", CONFIG['telegram'])
    console.print(f"[yellow]📂 Report Directory: {target_dir}[/yellow]")

if __name__ == "__main__":
    app()