from core.tor_controller import TorController
from core.session_manager import SessionManager
from core.id_manager import RandomIDManager
from core.pdf_downloader import PDFDownloader
import os
import time
import sys


ROTATION_INTERVAL = 5        # Rotate TOR every 5 requests
TOTAL_REQUESTS = 500         # Total requests to execute

# System Banner
def show_banner():
    print(r"""
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
~                                                               ~
~                          /\   /\                              ~
~                         /  \ /  \                             ~
~                        /    .    \                            ~
~                       /___________\                           ~
~                      ---------------                          ~
~             _.           _     _             _.               ~
~        ._ ./_.        '-(_)---(_)-'     ._ ./_.               ~
~          \|/                            ._\|/_.               ~
~   _____ _^|^_  ____    ____               \|/                 ~
~  |_   _/  _  \|  _ \  / ___|  ___ _ __ ___^|^___   ___ _ __   ~
~    | ||  | |  | |_) | \___ \ / __| '__/ _` | '_ \ / _ \ '__|  ~
~    | ||  |_|  |  _ <   ___) | (__| | | (_| | |_) |  __/ |     ~
~    |_| \_____/|_| \_\ |____/ \___|_|  \__,_| .__/ \___|_|     ~
~                                            |_|                ~
~                                                               ~
~    Author: FeathersMcgraw                                     ~
~    Pentesting Web Scraper                                     ~
~                                                               ~
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
""")

# Help Manu
def show_help():
    print("Use:")
    print("  python3 main.py <START_ID> <END_ID>")
    print("  python3 main.py --reset <START_ID> <END_ID>")
    print("")
    print("Examples:")
    print("  python3 main.py 1968000 1969000")
    print("  python3 main.py --reset 1968000 1969000")
    print("")
    print("Description:")
    print("  Run the system using a range of IDs to query files")
    print("  and download them through TOR.")
    print("")
    print("  --reset: removes history (used_ids) from the given range,")
    print("           allowing you to completely reuse that range.\n")


def parse_arguments():
    # -help
    if len(sys.argv) == 2 and sys.argv[1] == "-h":
        show_help()
        sys.exit(0)

    # --reset
    if len(sys.argv) == 4 and sys.argv[1] == "--reset":
        try:
            start_id = int(sys.argv[2])
            end_id = int(sys.argv[3])

            if start_id >= end_id:
                raise ValueError

            reset_used_ids(start_id, end_id)
            print(f"\n[OK] Successfully deleted range history: {start_id} → {end_id}\n")
            sys.exit(0)

        except ValueError:
            print("[ERROR] Invalid parameters for --reset.")
            print("Use: python3 main.py --reset <START_ID> <END_ID>")
            sys.exit(1)

    # Normal system run
    if len(sys.argv) != 3:
        print("[ERROR] Invalid parameters.")
        print("Use: python3 main.py -h to show help.")
        sys.exit(1)

    try:
        start_id = int(sys.argv[1])
        end_id = int(sys.argv[2])

        if start_id >= end_id:
            raise ValueError

        return start_id, end_id

    except ValueError:
        print("[ERROR] Parameters must be integers and start_id < end_id.")
        sys.exit(1)

# Reset range
def reset_used_ids(start_id, end_id, folder="data/"):
    """
    Delete the used IDs file corresponding to the range.
    """
    filename = f"used_ids_{start_id}_{end_id}.txt"
    full_path = os.path.join(folder, filename)

    if os.path.exists(full_path):
        os.remove(full_path)
        print(f"[INFO] Deleted file: {full_path}")
    else:
        print(f"[INFO] There is no history for the rank {start_id} → {end_id}. Nothing to delete.")

# Main
if __name__ == "__main__":

    show_banner()

    # Get range from parameters
    start_id, end_id = parse_arguments()
    print(f"[INFO] Selected ID range: {start_id} → {end_id}\n")

    # Initialize TOR
    tor = TorController()

    print("[INFO] Requesting initial TOR IP...")
    initial_ip = tor.refresh_ip()

    if initial_ip is None:
        print("\n[CRITICAL] ❌ Could not get an initial IP from TOR.")
        print("[CRITICAL] Aborting system execution.\n")
        sys.exit(1)

    print(f"[OK] Initial TOR IP: {initial_ip}\n")

    # SessionManager (by TOR)
    session_manager = SessionManager(
        user_agents_file="config/user_agents.txt", #Get user agents
        proxy="socks5h://127.0.0.1:9050"
    )

    # ID Manager (file by range)
    id_manager = RandomIDManager(
        start_id=start_id,
        end_id=end_id,
        used_ids_folder="data/"   # Folder where files will be saved by range
    )

    batch = id_manager.get_batch(TOTAL_REQUESTS)

    # PDF Downloader
    pdf_downloader = PDFDownloader(session_manager)

    # Iterate URLs
    pdf_urls = [
        f"https://YOUR.DOMAIN.HERE.COM.AR/EXAMPLES/EXAMPLE/xxxx-xx-EXAMPLE-X-xxxxxx-{invoice_id}.pdf" # <- Set your URL to iterate
        for invoice_id in batch
    ]

    print(f"\n===== Executing {TOTAL_REQUESTS} requests with rotation every {ROTATION_INTERVAL} =====")

    # MAIN LOOP WITH ROTATION + Ctrl+C + TOR error handling
    try:
        for i, url in enumerate(pdf_urls, start=1):

            print(f"\n[REQ {i}/{TOTAL_REQUESTS}] → {url}")

            result = pdf_downloader.download(url)

            # If it detects WAF blocking → rotate IP and regenerate session
            if result == "blocked":
                print("[!] WAF detected → Rotating TOR IP now...")
                new_ip = tor.rotate_ip()

                if new_ip is None:
                    print("\n[CRITICAL] ❌ Could not get an IP after rotating after crash.")
                    print("[CRITICAL] Aborting system.\n")
                    sys.exit(1)

                session_manager.create_new_session()
                time.sleep(3)

            # Scheduled rotation
            if i % ROTATION_INTERVAL == 0:
                print("\n[+] TOR scheduled rotation...")

                new_ip = tor.rotate_ip()
                if new_ip is None:
                    print("\n[CRITICAL] ❌ Could not obtain a valid IP after scheduled rotation.")
                    print("[CRITICAL] Aborting system.\n")
                    sys.exit(1)

                session_manager.create_new_session()
                time.sleep(3)
                print("[+] New TOR IP:", new_ip)

        print(f"\n===== ✔ [FINISH] → {TOTAL_REQUESTS} requests completed successfully =====\n")

    except KeyboardInterrupt:
        print("\n[!] Interruption detected. Leaving in a controlled manner...")
        print("[!] The system stopped without errors.\n")
