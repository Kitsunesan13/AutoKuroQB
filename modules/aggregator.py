import os
import json
from datetime import datetime

def parse_nuclei_report_gen(filepath):
    if not os.path.exists(filepath): return []
    results = []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            results = [line.strip() for line in f if line.strip()]
    except: pass
    return results

def file_to_list_gen(filepath):
    if not os.path.exists(filepath): return []
    try:
        with open(filepath, 'r', errors='ignore') as f:
            return [line.strip() for line in f if line.strip()]
    except: return []

def generate_json_report(domain, output_dir):
    report = {
        "target": domain,
        "scan_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "recon": {
            "live_hosts": file_to_list_gen(os.path.join(output_dir, "live_hosts.txt")),
            "open_ports": file_to_list_gen(os.path.join(output_dir, "open_ports.txt")),
            "technologies": parse_nuclei_report_gen(os.path.join(output_dir, "technology.txt")),
            "cloud_assets": parse_nuclei_report_gen(os.path.join(output_dir, "cloud_enum_results.txt")),
            "subdomain_takeovers": parse_nuclei_report_gen(os.path.join(output_dir, "takeover_results.txt"))
        },
        "discovery": {
            "hidden_directories": file_to_list_gen(os.path.join(output_dir, "hidden_dirs.txt")),
            "parameters": file_to_list_gen(os.path.join(output_dir, "parameters.txt"))
        },
        "vulnerabilities": {
            "nuclei_general": parse_nuclei_report_gen(os.path.join(output_dir, "nuclei_report.txt")),
            "nuclei_context": parse_nuclei_report_gen(os.path.join(output_dir, "nuclei_report_context.txt")),
            "secrets_js": parse_nuclei_report_gen(os.path.join(output_dir, "nuclei_report_secrets.txt")),
            "secrets_trufflehog": file_to_list_gen(os.path.join(output_dir, "secrets_leak.txt")),
            "xss_dalfox": file_to_list_gen(os.path.join(output_dir, "dalfox_xss.txt"))
        }
    }
    
    try:
        count = 0
        with open(os.path.join(output_dir, "all_urls_clean.txt"), 'r') as f:
            for _ in f: count += 1
        report["discovery"]["crawled_urls_count"] = count
    except: report["discovery"]["crawled_urls_count"] = 0

    json_path = os.path.join(output_dir, "final_report.json")
    with open(json_path, 'w') as f: json.dump(report, f, indent=4)
    return json_path