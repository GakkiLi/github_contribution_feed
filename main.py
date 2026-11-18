#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run.py  —— Single-repo multi-year contribution graph (Jan 1 start)
- 365/366 days per year, no more 371 days
- All commits are appended to the same folder contribution_art
"""

import os
import sys
import shutil
import subprocess
import logging
import calendar
from datetime import datetime, timedelta

from contribution_pattern import LEVELS, generate_pattern, validate_calendar_range

REPO_NAME = "contribution_art"

# ------------------ utilities ------------------
def ask(prompt, default=None, cast=str):
    while True:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            value = default
        if value is None:
            print("Value cannot be empty, please re-enter!")
            continue
        try:
            return cast(value)
        except ValueError:
            print("Invalid format, please re-enter!")

def run_cmd(cmd, cwd, env=None):
    try:
        subprocess.run(cmd, cwd=cwd, check=True, shell=True,
                       text=True, capture_output=True, encoding="utf-8", env=env)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed: {cmd}\n{e.stderr}")
        return False

def is_git_repo(path):
    return run_cmd("git rev-parse --is-inside-work-tree", path)

# ------------------ core ------------------
def build_year_in_repo(year, repo_path, user_name, user_email):
    """Append commits for a given year (starting Jan 1)"""
    days = 366 if calendar.isleap(year) else 365
    start_date = datetime(year, 1, 1)
    pattern = generate_pattern(start_date.date(), days)

    readme_path = os.path.join(repo_path, "README.md")
    counter = 0
    if os.path.isfile(readme_path):
        import re
        with open(readme_path, encoding="utf-8") as f:
            m = re.findall(r"Commit #(\d+)", f.read())
            counter = int(m[-1]) if m else 0

    for idx, level in enumerate(pattern, 1):
        commits = LEVELS.get(str(level), 0)
        if commits <= 0:
            continue
        cur_date = start_date + timedelta(days=idx - 1)
        for _ in range(commits):
            counter += 1
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(f"Commit #{counter} on {cur_date.date()}\n")
            if not run_cmd("git add README.md", repo_path):
                return False
            env = os.environ.copy()
            env.update({
                "GIT_AUTHOR_DATE": cur_date.isoformat(),
                "GIT_COMMITTER_DATE": cur_date.isoformat(),
            })
            if not run_cmd(f'git commit -m "feat: commit #{counter}"',
                           repo_path, env):
                return False

        # Progress bar
        perc = idx / days * 100
        sys.stdout.write(f"\r{year}: {perc:5.1f}% ({idx}/{days})  commit #{counter}")
        sys.stdout.flush()
    print()
    logging.info(f"Year {year} appended, total commits: {counter}")
    return True

# ------------------ main flow ------------------
def main():
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(message)s",
                        stream=sys.stdout)

    print("=== Single-repo multi-year contribution graph (Jan 1 start) ===")
    user_name = ask("Github username", default="username")
    user_email = ask("Git email", default="user@mail.com")
    start_year = ask("Start year", cast=int)
    end_year = ask("End year", cast=int)
    remote_url = ask("GitHub repository URL (https/ssh)", default="https://github.com/username/project_name")

    if start_year > end_year:
        print("\033[31mStart year must be less than or equal to end year!\033[0m")
        sys.exit(1)

    if start_year < 2008 or end_year < 2008:
        print("\033[31m⚠️  GitHub was founded in 2008. "
              "Faking contributions before 2008 may get your account suspended!\033[0m")
        sys.exit(1)

    try:
        validate_calendar_range(datetime(start_year, 1, 1).date(),
                                datetime(end_year, 12, 31).date())
    except NotImplementedError as error:
        logging.error(f"Mainland China holiday calendar does not cover this range: {error}. "
                      "Run python -m pip install --upgrade -r requirements.txt; "
                      "if still unsupported, shorten the range or wait for a calendar update.")
        sys.exit(1)
    logging.info("Using mainland China calendar (including makeup workdays); "
                 "rest days: 90% no commits, 10% one commit.")

    repo_path = os.path.abspath(REPO_NAME)

    # Initialize or update repo
    if os.path.exists(repo_path):
        if not is_git_repo(repo_path):
            logging.error(f"{repo_path} exists but is not a Git repository!")
            sys.exit(1)
        if not run_cmd("git pull --rebase", repo_path):
            sys.exit(1)
    else:
        os.makedirs(repo_path, exist_ok=True)
        cmds = ("git init",
                f'git config user.name "{user_name}"',
                f'git config user.email "{user_email}"')
        for cmd in cmds:
            if not run_cmd(cmd, repo_path):
                sys.exit(1)

    # Append year by year
    for year in range(start_year, end_year + 1):
        if not build_year_in_repo(year, repo_path, user_name, user_email):
            logging.error(f"Processing year {year} failed, aborting.")
            sys.exit(1)

    print("\n\033[32m🎉 All years have been appended to the same repository!\033[0m")
    print(f"Directory: {repo_path}")

    if remote_url.strip():
        print("Pushing to GitHub automatically ...")
        cmds = [
            f"git remote get-url origin || git remote add origin {remote_url}",
            "git branch -M main",
            "git push -u origin main"
        ]
        for cmd in cmds:
            if not run_cmd(cmd, repo_path):
                logging.error("Automatic push failed, please handle it manually!")
                sys.exit(1)
        print("\033[32mSuccessfully pushed to GitHub!\033[0m")
    else:
        print("\033[33mNo repository URL provided, please push manually later!\033[0m")


if __name__ == "__main__":
    main()