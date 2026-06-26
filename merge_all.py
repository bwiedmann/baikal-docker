#!/usr/bin/env python3
import json
import subprocess
import sys

def run_cmd(cmd, check=True, capture_output=True):
    """Run a shell command and return stdout/stderr."""
    try:
        res = subprocess.run(
            cmd,
            shell=True,
            text=True,
            capture_output=capture_output,
            check=check
        )
        return res.stdout.strip() if res.stdout else ""
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.strip() if e.stderr else ""
        stdout_msg = e.stdout.strip() if e.stdout else ""
        raise RuntimeError(f"Command '{cmd}' failed with exit code {e.returncode}.\nStdout: {stdout_msg}\nStderr: {stderr_msg}")

def main():
    print("=== Starting Merge Script ===")
    
    # 1. Ensure git is clean
    status = run_cmd("git status --porcelain")
    if status:
        print("Error: Git working directory is not clean. Please commit or stash changes.")
        print(status)
        sys.exit(1)
        
    # 2. Check if main branch exists, or master
    branches = run_cmd("git branch --list").split()
    # Normalize list
    branches = [b.replace("*", "").strip() for b in branches]
    
    has_main = "main" in branches
    has_master = "master" in branches
    
    if not has_main:
        if has_master:
            print("Branch 'main' not found. Creating 'main' from 'master'.")
            run_cmd("git checkout -b main master")
        else:
            print("Neither 'main' nor 'master' branches found locally.")
            # Let's see if origin/master or origin/main exists
            all_branches = run_cmd("git branch -a")
            if "origin/master" in all_branches:
                print("Creating 'main' from 'origin/master'.")
                run_cmd("git checkout -b main origin/master")
            elif "origin/main" in all_branches:
                print("Creating 'main' from 'origin/main'.")
                run_cmd("git checkout -b main origin/main")
            else:
                print("Error: Could not identify a base branch (master or main) to start from.")
                sys.exit(1)
    else:
        print("Switching to 'main' branch.")
        run_cmd("git checkout main")

    # Fetch latest remote changes
    print("Fetching from origin...")
    run_cmd("git fetch origin")

    # 3. Get remote branches to merge
    remote_branches_raw = run_cmd("git branch -r").split("\n")
    remote_branches = []
    for rb in remote_branches_raw:
        rb = rb.strip()
        if not rb or "->" in rb:
            continue
        # We only want origin branches, excluding main, master
        if rb.startswith("origin/"):
            branch_name = rb[len("origin/"):]
            if branch_name not in ["main", "master"]:
                remote_branches.append(rb)

    print(f"Found {len(remote_branches)} remote branches to merge.")
    
    merged_branches = []
    failed_branches = []

    for rb in remote_branches:
        print(f"Merging {rb} into main...")
        try:
            run_cmd(f"git merge {rb} --no-edit")
            print(f"Successfully merged {rb}")
            merged_branches.append(rb)
        except RuntimeError as e:
            print(f"Conflict or error merging {rb}. Aborting merge.")
            run_cmd("git merge --abort")
            failed_branches.append((rb, str(e)))

    # 4. Fetch PRs from the base fork repository (ckulka/baikal-docker)
    print("\nRetrieving open PRs from the fork base repository (ckulka/baikal-docker)...")
    try:
        prs_json = run_cmd("gh pr list --repo ckulka/baikal-docker --json number,title,headRefName,headRepositoryOwner --limit 100")
        prs = json.loads(prs_json)
    except Exception as e:
        print(f"Error querying PRs using GitHub CLI: {e}")
        print("Please ensure 'gh' is installed and you are authenticated.")
        sys.exit(1)

    print(f"Found {len(prs)} open PRs to merge.")
    
    merged_prs = []
    failed_prs = []

    for pr in prs:
        pr_num = pr["number"]
        pr_title = pr["title"]
        print(f"Fetching and merging PR #{pr_num}: '{pr_title}'...")
        try:
            # Fetch the PR head commit directly from the base repo
            run_cmd(f"git fetch https://github.com/ckulka/baikal-docker.git pull/{pr_num}/head")
            # Merge FETCH_HEAD
            run_cmd(f"git merge FETCH_HEAD --no-edit -m \"Merge PR #{pr_num}: {pr_title}\"")
            print(f"Successfully merged PR #{pr_num}")
            merged_prs.append(pr_num)
        except RuntimeError as e:
            print(f"Conflict or error merging PR #{pr_num}. Aborting merge.")
            run_cmd("git merge --abort")
            failed_prs.append((pr_num, pr_title, str(e)))

    # 5. Summary
    print("\n" + "="*40)
    print("=== MERGE SUMMARY ===")
    print(f"Successfully merged branches ({len(merged_branches)}):")
    for mb in merged_branches:
        print(f" - {mb}")
    print(f"Failed to merge branches ({len(failed_branches)}):")
    for fb, err in failed_branches:
        print(f" - {fb} (Conflict/Error)")

    print(f"\nSuccessfully merged PRs ({len(merged_prs)}):")
    for mp in merged_prs:
        print(f" - PR #{mp}")
    print(f"Failed to merge PRs ({len(failed_prs)}):")
    for fp_num, fp_title, err in failed_prs:
        print(f" - PR #{fp_num}: {fp_title} (Conflict/Error)")
    print("="*40)

if __name__ == "__main__":
    main()
