#!/usr/bin/env python3
"""
Office Badminton Auction Tracker
---------------------------------
Run this script during the live auction. The auctioneer enters:
  1. the team the player was sold to
  2. the player's name
  3. the cost (tokens)

It tracks each team's remaining purse, enforces the rules (25,000 token
purse, 3 players to buy per team), and saves everything to a local JSON
file after every action so you can close and reopen the script without
losing data.
"""

import json
import os
import sys
from datetime import datetime

PURSE = 25000
SLOTS = 3
NUM_TEAMS = 10
SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auction_data.json")


# ---------------------------------------------------------------------------
# State handling
# ---------------------------------------------------------------------------

def default_state():
    return {
        "teams": [
            {"id": i, "name": f"Team {i}", "captain": "", "players": []}
            for i in range(1, NUM_TEAMS + 1)
        ],
        "log": [],
    }


def load_state():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            return json.load(f)
    return default_state()


def save_state(state):
    with open(SAVE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def spent(team):
    return sum(p["cost"] for p in team["players"])


def remaining(team):
    return PURSE - spent(team)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def print_header(state):
    sold = sum(len(t["players"]) for t in state["teams"])
    filled = sum(1 for t in state["teams"] if len(t["players"]) >= SLOTS)
    spent_total = sum(spent(t) for t in state["teams"])
    print("=" * 60)
    print("  OFFICE BADMINTON AUCTION".center(60))
    print("=" * 60)
    print(f"  Teams filled : {filled}/{NUM_TEAMS}    "
          f"Players sold : {sold}/{NUM_TEAMS * SLOTS}    "
          f"Tokens spent : {spent_total:,}")
    if state["log"]:
        last = state["log"][-1]
        team_name = next((t["name"] for t in state["teams"] if t["id"] == last["team_id"]), "?")
        print(f"  Last sale    : {last['player']} -> {team_name} for {last['cost']:,} tokens")
    print("=" * 60)


def print_teams(state):
    print()
    for t in state["teams"]:
        rem = remaining(t)
        bar_len = 20
        filled_len = max(0, min(bar_len, round(bar_len * rem / PURSE)))
        bar = "#" * filled_len + "-" * (bar_len - filled_len)
        flag = " (FULL)" if len(t["players"]) >= SLOTS else ""
        cap = f" - {t['captain']}" if t["captain"] else ""
        print(f"[{t['id']:>2}] {t['name']}{cap}{flag}")
        print(f"      [{bar}] {rem:,}/{PURSE:,} left   slots: {len(t['players'])}/{SLOTS}")
        if t["players"]:
            for p in t["players"]:
                print(f"        - {p['name']} ({p['cost']:,})")
        print()


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------

def pick_team(state, prompt="Team number"):
    while True:
        raw = input(f"{prompt} (1-{NUM_TEAMS}, or 'c' to cancel): ").strip()
        if raw.lower() == "c":
            return None
        if not raw.isdigit() or not (1 <= int(raw) <= NUM_TEAMS):
            print("  Enter a number between 1 and", NUM_TEAMS)
            continue
        team = next(t for t in state["teams"] if t["id"] == int(raw))
        return team


def record_sale(state):
    team = pick_team(state, "Sold to which team")
    if team is None:
        return
    if len(team["players"]) >= SLOTS:
        print(f"  {team['name']} already has {SLOTS} players. Can't add more.")
        input("  Press Enter to continue...")
        return

    name = input("Player name: ").strip()
    if not name:
        print("  Player name can't be empty.")
        input("  Press Enter to continue...")
        return

    # Warn on duplicate player name across teams
    for t in state["teams"]:
        if any(p["name"].lower() == name.lower() for p in t["players"]):
            confirm = input(f"  '{name}' is already sold to {t['name']}. Add anyway? (y/N): ")
            if confirm.lower() != "y":
                return
            break

    raw_cost = input("Cost (tokens): ").strip()
    if not raw_cost.isdigit() or int(raw_cost) <= 0:
        print("  Enter a valid positive number for cost.")
        input("  Press Enter to continue...")
        return
    cost = int(raw_cost)

    if cost > remaining(team):
        print(f"  {team['name']} only has {remaining(team):,} tokens left. "
              f"Can't spend {cost:,}.")
        input("  Press Enter to continue...")
        return

    team["players"].append({"name": name, "cost": cost})
    state["log"].append({
        "team_id": team["id"],
        "player": name,
        "cost": cost,
        "ts": datetime.now().isoformat(timespec="seconds"),
    })
    save_state(state)
    print(f"  Sold: {name} -> {team['name']} for {cost:,} tokens. Saved.")
    input("  Press Enter to continue...")


def undo_last_sale(state):
    if not state["log"]:
        print("  Nothing to undo.")
        input("  Press Enter to continue...")
        return
    last = state["log"].pop()
    team = next(t for t in state["teams"] if t["id"] == last["team_id"])
    for i, p in enumerate(team["players"]):
        if p["name"] == last["player"] and p["cost"] == last["cost"]:
            team["players"].pop(i)
            break
    save_state(state)
    print(f"  Undone: {last['player']} removed from {team['name']}.")
    input("  Press Enter to continue...")


def edit_team_info(state):
    team = pick_team(state, "Edit which team")
    if team is None:
        return
    new_name = input(f"  Team name [{team['name']}]: ").strip()
    new_captain = input(f"  Captain name [{team['captain']}]: ").strip()
    if new_name:
        team["name"] = new_name
    if new_captain:
        team["captain"] = new_captain
    save_state(state)
    print("  Saved.")
    input("  Press Enter to continue...")


def export_summary(state):
    out_path = os.path.join(os.path.dirname(SAVE_FILE), "auction_results.txt")
    with open(out_path, "w") as f:
        f.write("OFFICE BADMINTON AUCTION RESULTS\n")
        f.write("=" * 40 + "\n\n")
        for t in state["teams"]:
            f.write(f"{t['name']} (Captain: {t['captain'] or 'TBD'})\n")
            f.write(f"  Remaining purse: {remaining(t):,} / {PURSE:,}\n")
            for p in t["players"]:
                f.write(f"  - {p['name']} : {p['cost']:,}\n")
            f.write("\n")
    print(f"  Summary written to {out_path}")
    input("  Press Enter to continue...")


def reset_auction(state):
    confirm = input("  This clears ALL data. Type 'RESET' to confirm: ")
    if confirm == "RESET":
        new_state = default_state()
        save_state(new_state)
        print("  Auction reset.")
        input("  Press Enter to continue...")
        return new_state
    print("  Cancelled.")
    input("  Press Enter to continue...")
    return state


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

MENU = """
  [1] Record a sale
  [2] Undo last sale
  [3] Edit team / captain name
  [4] Export summary (.txt)
  [5] Reset auction (clears everything)
  [q] Quit
"""


def main():
    state = load_state()
    while True:
        clear()
        print_header(state)
        print_teams(state)
        print(MENU)
        choice = input("Choose an option: ").strip().lower()

        if choice == "1":
            record_sale(state)
        elif choice == "2":
            undo_last_sale(state)
        elif choice == "3":
            edit_team_info(state)
        elif choice == "4":
            export_summary(state)
        elif choice == "5":
            state = reset_auction(state)
        elif choice == "q":
            print("Data saved to", SAVE_FILE)
            sys.exit(0)
        else:
            print("  Not a valid option.")
            input("  Press Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting. Data already saved to", SAVE_FILE)``