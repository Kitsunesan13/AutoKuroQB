import os

def analyze_tech_stack(tech_file, rules):
    detected_tags = set()
    if not os.path.exists(tech_file): return ""
    try:
        content = open(tech_file, 'r', errors='ignore').read().lower()
        for tech, tags in rules.items():
            if tech in content:
                for tag in tags.split(','): detected_tags.add(tag)
    except: pass
    if not detected_tags: return ""
    return ",".join(detected_tags)

def group_targets_smartly(live_hosts_file, output_dir):
    groups = {"api": [], "static": [], "dynamic": []}
    files = {
        "api": os.path.join(output_dir, "targets_api.txt"),
        "static": os.path.join(output_dir, "targets_static.txt"),
        "dynamic": os.path.join(output_dir, "targets_dynamic.txt")
    }

    if not os.path.exists(live_hosts_file): return files

    with open(live_hosts_file, 'r', errors='ignore') as f:
        for line in f:
            url = line.strip()
            if not url: continue
            url_lower = url.lower()

            if "api." in url_lower or "/api" in url_lower or "v1" in url_lower or "graphql" in url_lower:
                groups["api"].append(url)
            elif "cdn." in url_lower or "static." in url_lower or "assets." in url_lower or "img." in url_lower:
                groups["static"].append(url)
            else:
                groups["dynamic"].append(url)

    for key, path in files.items():
        if groups[key]:
            with open(path, 'w') as f: f.write('\n'.join(groups[key]))
    return files