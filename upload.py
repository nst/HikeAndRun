#!/usr/bin/env python3

import ftplib
import os
import json
import sys

# Configuration
TIMESTAMP_FILE = "last_upload.txt"
CONFIG_FILE = "upload_config.json"

# Optimization: 128KB buffer size (vs default 8KB) for faster uploads
UPLOAD_BLOCK_SIZE = 128 * 1024 

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: {CONFIG_FILE} not found.")
        print("Please create it with: { 'host': '...', 'user': '...', 'password': '...', 'local_dir': '...', 'remote_dir': '...' }")
        sys.exit(1)
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def get_files_to_upload(local_dir, last_upload_ts):
    """
    Scans the directory locally to determine what needs to be sent.
    Returns a list of descriptions (strings) for the user to review.
    """
    changes = []
    
    # os.walk is easier for a flat scan than manual recursion
    for root, dirs, files in os.walk(local_dir):
        # Modify dirs in-place to skip hidden directories
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        
        for name in files:
            if name.startswith("."): continue
            if name == TIMESTAMP_FILE: continue

            local_path = os.path.join(root, name)
            
            # Calculate relative path for display (e.g. "subdir/image.jpg")
            rel_path = os.path.relpath(local_path, local_dir)

            if os.path.getmtime(local_path) >= last_upload_ts:
                changes.append(f"[FILE] {rel_path}")
    
    return sorted(changes)

def upload_recursive(ftp, local_dir, remote_path, last_upload_ts):
    """
    Recursively uploads files. Assumes user has already confirmed.
    """
    # --- ENTER REMOTE DIRECTORY ---
    try:
        ftp.cwd(remote_path)
    except ftplib.error_perm:
        if remote_path not in ["/", "."]:
            try:
                ftp.mkd(remote_path)
                print(f"  [MKD] Created remote dir: {remote_path}")
                ftp.cwd(remote_path)
            except ftplib.error_perm as e:
                print(f"  [ERR] Could not create {remote_path}: {e}")
                return

    # --- SCAN LOCAL FILES ---
    for name in os.listdir(local_dir):
        if name.startswith("."): continue
        if name == TIMESTAMP_FILE: continue

        local_path = os.path.join(local_dir, name)
        
        # 1. FILE UPLOAD
        if os.path.isfile(local_path):
            file_ts = os.path.getmtime(local_path)
            
            if file_ts >= last_upload_ts:
                print(f"  [STOR] Uploading {name}...")
                try:
                    with open(local_path, 'rb') as f:
                        # Optimization: Use larger block size
                        ftp.storbinary(f'STOR {name}', f, blocksize=UPLOAD_BLOCK_SIZE)
                except Exception as e:
                    print(f"  [ERR] Failed to upload {name}: {e}")

        # 2. RECURSIVE DIRECTORY
        elif os.path.isdir(local_path):
            # We don't need to check timestamp for dirs, just recurse
            # The MKD check happens at the start of the called function
            upload_recursive(ftp, local_path, name, last_upload_ts)
            
            # Step back up after recursion
            ftp.cwd("..")

def main():
    # 1. Load Configuration
    config = load_config()
    
    required_keys = ['host', 'user', 'password', 'local_dir', 'remote_dir']
    missing_keys = [k for k in required_keys if k not in config]
    if missing_keys:
        print(f"Error: Missing keys in {CONFIG_FILE}: {', '.join(missing_keys)}")
        sys.exit(1)

    local_dir = config['local_dir']
    remote_dir = config['remote_dir']

    if not os.path.exists(local_dir):
        print(f"Error: Local directory '{local_dir}' does not exist.")
        return

    # 2. Check Timestamp
    if os.path.isfile(TIMESTAMP_FILE):
        last_upload_ts = os.path.getmtime(TIMESTAMP_FILE)
        print(f"--- Last upload was: {last_upload_ts} ---")
    else:
        last_upload_ts = 0.0
        print("--- First run: Uploading ALL files ---")

    # 3. Scan and List
    print(f"\nScanning '{local_dir}' for changes...")
    pending_files = get_files_to_upload(local_dir, last_upload_ts)

    if not pending_files:
        print("No new or modified files found.")
        print("Everything is up to date.")
        return

    print(f"\n--- Files to be uploaded to '{remote_dir}' ---")
    for f in pending_files:
        print(f)
    print("----------------------------------------------")

    # 4. Confirmation
    confirm = input(f"Proceed with upload of {len(pending_files)} files? [y/N]: ").strip().lower()
    if confirm != 'y':
        print("Upload cancelled.")
        return

    # 5. Connect and Upload
    try:
        print(f"\nConnecting to {config['host']}...")
        with ftplib.FTP(config['host'], config['user'], config['password']) as ftp:
            print(f"Connected. Starting upload...")
            
            upload_recursive(ftp, local_dir, remote_dir, last_upload_ts)
        
        # 6. Update Timestamp (only on success)
        with open(TIMESTAMP_FILE, 'w') as f:
            f.write("timestamp") 
        print("\nDone. Timestamp updated.")

    except Exception as e:
        print(f"\n[Error] Connection or Upload failed: {e}")

if __name__ == "__main__":
    main()