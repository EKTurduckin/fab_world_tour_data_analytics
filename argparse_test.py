import argparse
import csv
import requests
import re
from bs4 import BeautifulSoup
from dataclasses import dataclass

DATABASE = "fab_world_tour.db"

@dataclass
class Event:
    """A Flesh and Blood tournament"""
    url_name: str
    display_name: str
    event_type: str
    rounds_total: int
    draft_rounds_start: int
    draft_rounds_end: int

    @property
    def constructed_rounds(self) -> list[int]:
        draft_rounds = {_ for _ in range(self.draft_rounds_start, self.draft_rounds_end + 1)}
        return [round_ for round_ in range(1, self.rounds_total + 1) if round_ not in draft_rounds]
    
@dataclass
class Pairings:
    """Pairing Information for a Flesh and Blood tournament"""
    name: str
    round: int
    table: int
    seat: int
    gem_id: int
    round_outcome: str

def selection_method():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand")
    subparsers.required = True

    parser_bulk = subparsers.add_parser("bulk")
    parser_bulk.add_argument("file", type=str)
    # parser_bulk.add_argument("-b", "--bulk", action="store_false", help="I'm cheating to make this work. Don't add this flag")

    parser_manual = subparsers.add_parser("manual")
    parser_manual.add_argument("name", metavar="name", type=str, help="Enter the event name found in the URL of fabtcg.com.\nex. pro-tour-london")
    parser_manual.add_argument("display_name", metavar="display_name", type=str, help="Enter the event name as you'd like it displayed.")
    parser_manual.add_argument("total_rounds", metavar="total_rounds", type=int, help="Number of rounds in the tournament.")
    parser_manual.add_argument("-s", "--draft_start", metavar="draft_start", type=int, help="Draft starts in round ? of tournament.")
    parser_manual.add_argument("-e", "--draft_end", metavar="draft_end", type=int, help="Draft ends in round ? of tournament.")
    # parser_manual.add_argument("-m", "--manual", action="store_false", help="I'm cheating to make this work. Don't add this flag")

    return parser.parse_args()

def create_event_object(selection_method):
    output = []
    draft_start = selection_method.draft_start or 0
    draft_end = selection_method.draft_end or 0

    output.append(Event(selection_method.name, selection_method.display_name, selection_method.total_rounds, draft_start, draft_end))

    return output

def create_events_bulk(selection_method):
    output = []
    with open(selection_method.file) as file:
        reader = csv.DictReader(file)

        for row in reader:
            draft_start = row["draft_rounds_start"] or 0
            draft_end = row["draft_rounds_end"] or 0

            output.append(
                Event(
                    url_name=row["url_name"],
                    display_name=row["display_name"],
                    event_type=row["event_type"],
                    rounds_total=row["rounds_total"],
                    draft_rounds_start=draft_start,
                    draft_rounds_end=draft_end
                )
            )

    return output

def get_pairings(event, constructed_rounds):
    output = []
    url = "https://fabtcg.com/en/coverage/{}/results/{}/"

    for round in constructed_rounds:
        # Consider adding error handling. If there's a problem fetching the page for one round should fetching
        # all other rounds fail? "Yes" is a totally fine answer, to that question. The important part is to
        # intentionally make a decision and understand the potential consequences.

        page = requests.get(url.format(event, round))
        soup = BeautifulSoup(page.text, "html")

        player = soup.find_all("div", {"class":"tournament-coverage__player-hero-and-deck"})
        winner = soup.find_all("div", {"class":"tournament-coverage__result"})

        for idx, id in enumerate(player):
            table = idx // 2 + 1

            seat = (idx % 2) + 1

            gem_id = id.find("a", href = True)

            if gem_id:
                gem_id = re.search(r"\/(\d+)", gem_id["href"]).group(1)

            if re.search(r"(\d)", winner[table - 1].text):
                winning_seat = int(re.search(r"(\d)", winner[table - 1].text).group(1))
            else:
                # print(f"Round: {round} Table: {table} had a draw")
                winning_seat = 0

            if winning_seat == 0:
                player_status = "Draw"
            elif winning_seat == seat:
                player_status = "Win"
            else:
                player_status = "Loss"

            # Consider using a self documenting data structure like a namedtuple or a dataclass to hold
            # this information instead of using a list. Future developers (including yourself in six months)
            # will appreciate it.
            record = [event, round, table, seat, gem_id, player_status]

            output.append(record)

    return output

event_args = selection_method()

if event_args.subcommand == "bulk":
    event_meta_data = create_events_bulk(event_args)
if event_args.subcommand == "manual":
    event_meta_data = create_event_object(event_args)

