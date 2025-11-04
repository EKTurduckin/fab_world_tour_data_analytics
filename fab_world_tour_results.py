# %%
import csv
import requests
import re
import argparse
import sqlite3
from bs4 import BeautifulSoup
from dataclasses import dataclass, astuple, field


DATABASE = "fab_world_tour.db"

@dataclass
class Seat:
    """A seat in a match of a tournament and it's outcome."""
    event: str
    round: int
    table: int
    seat: int
    gem_id: int
    match_outcome: str

    @property
    def table_id(self) -> int:
        """Concat of round number and table"""
        return self.round * 10 + self.table

@dataclass
class Event:
    """A Flesh and Blood tournament"""
    url_name: str
    display_name: str
    event_type: str
    rounds_total: int
    draft_rounds_start: int
    draft_rounds_end: int
    pairings: list[object] = field(default_factory=list)
    players: list[object] = field(default_factory=list) #inserting Player class

    @property
    def constructed_rounds(self) -> list[int]:
        draft_rounds = {_ for _ in range(self.draft_rounds_start, self.draft_rounds_end + 1)}
        return [round_ for round_ in range(1, self.rounds_total + 1) if round_ not in draft_rounds]

    @property
    def attendees(self) -> set[int]:
        return set(seat.gem_id for seat in self.pairings)
    
@dataclass
class Card:
    card_import: str

    def __post_init__(self):
        self.card_split: list[str] = re.split(r" x | \(", self.card_import)

    @property
    def copies(self) -> int:
        return int(self.card_split[0])
    
    @property
    def pitch(self) -> int:
        if len(self.card_split) > 2:
            if self.card_split[2] == "blu)":
                return 3
            if self.card_split[2] == "yel)":
                return 2
            if self.card_split[2] == "red)":
                return 1
    
    @property  
    def card_name(self) -> str:
        return self.card_split[1]
    
@dataclass
class Player:
    player_import: str
    event_date: str
    format: str
    hero: str
    deck: list[str] = field(default_factory=list)
    cards: list[object] = field(default_factory=list)

    @property
    def player_name(self) -> str:
        return re.search(r"^(.*?)\s*\((\d+)\)$", self.player_import).group(1)
    
    @property
    def gem_id(self) -> int:
        return re.search(r"^(.*?)\s*\((\d+)\)$", self.player_import).group(2)

def event_entry():
    # debug_arg_string = "bulk events.csv".split()

    def create_event_single(parsed_arguments):
        output = []
        draft_start = parsed_arguments.draft_start or 0
        draft_end = parsed_arguments.draft_end or 0

        output.append(Event(parsed_arguments.name, parsed_arguments.display_name, parsed_arguments.total_rounds, draft_start, draft_end))

        return output

    def create_events_bulk(parsed_arguments):
        output = []
        with open(parsed_arguments.file) as file:
            reader = csv.DictReader(file)

            for row in reader:
                draft_start = row["draft_rounds_start"] or 0
                draft_end = row["draft_rounds_end"] or 0

                output.append(
                    Event(
                        url_name=row["url_name"],
                        display_name=row["display_name"],
                        event_type=row["event_type"],
                        rounds_total=int(row["rounds_total"]),
                        draft_rounds_start=int(draft_start),
                        draft_rounds_end=int(draft_end)
                    )
                )

        return output
    
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="subcommand")
    subparsers.required = True

    parser_bulk = subparsers.add_parser("bulk")
    parser_bulk.add_argument("file", type=str)

    parser_manual = subparsers.add_parser("manual")
    parser_manual.add_argument("name", metavar="name", type=str, help="Enter the event name found in the URL of fabtcg.com.\nex. pro-tour-london")
    parser_manual.add_argument("display_name", metavar="display_name", type=str, help="Enter the event name as you'd like it displayed.")
    parser_manual.add_argument("total_rounds", metavar="total_rounds", type=int, help="Number of rounds in the tournament.")
    parser_manual.add_argument("-s", "--draft_start", metavar="draft_start", type=int, help="Draft starts in round ? of tournament.")
    parser_manual.add_argument("-e", "--draft_end", metavar="draft_end", type=int, help="Draft ends in round ? of tournament.")

    parsed_arguments = parser.parse_args()

    if parsed_arguments.subcommand == "bulk":
        all_events = create_events_bulk(parsed_arguments)
    if parsed_arguments.subcommand == "manual":
        all_events = create_event_single(parsed_arguments)

    return all_events

def get_pairings(event):
    coverage_url = "https://fabtcg.com/en/coverage/{}/results/{}/"
    # TODO: Add error handling

    for round_number in event.constructed_rounds:
        print(f"\rGetting results round {round_number}/{event.rounds_total} for {event.display_name}", end="")
        page = requests.get(coverage_url.format(event.url_name, round_number))
        soup = BeautifulSoup(page.text, "html.parser")

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
                winning_seat = 0

            if winning_seat == 0:
                player_status = "Draw"
            elif winning_seat == seat:
                player_status = "Win"
            else:
                player_status = "Loss"
            
            event.pairings.append(Seat(
                event=event.url_name,
                round=round_number,
                table=table,
                seat=seat,
                gem_id=gem_id,
                match_outcome=player_status
                ))

    print(f"\nDone getting results for {event.display_name}")

def get_player_info(event):
    coverage_url = "https://fabtcg.com/en/coverage/{}/decklist/{}/"

    for idx, gem_id in enumerate(event.attendees):
        decklist_url = coverage_url.format(event.url_name, gem_id)

        page = requests.get(decklist_url)
        soup = BeautifulSoup(page.text, "html.parser")

        player_info = [data.text.strip() for data in soup.find_all("td")]
        if len(player_info) > 0:
                player_object = Player(
                    player_import=player_info[0],
                    event_date=player_info[1],
                    format=player_info[3],
                    hero=player_info[4],
                    deck=player_info[5:]
                )

                event.players.append(player_object)
                print(f"\rCollected {idx+1}/{len(event.attendees)} decklists", end="")
    print(f"\nDone getting decklists from {event.display_name}")

def post_events_to_sql(all_events):
    cnxn = sqlite3.connect(DATABASE)
    cursor = cnxn.cursor()
    insert_sql = "INSERT INTO events (url_name, display_name, event_type, rounds_total, draft_round_start, draft_round_end) VALUES (?, ?, ?, ?, ?, ?)"
    for event in all_events:
        payload = tuple((event.url_name, event.display_name, event.event_type, event.rounds_total, event.draft_rounds_start, event.draft_rounds_end))
        cursor.execute(insert_sql, payload)
    cursor.close()
    cnxn.commit()

def add_card_to_player(player):
    for card in player.deck:
        player.cards.append(
            Card(card)
        )

def post_cards_to_sql(player, event_url_name):
    insert_sql = """Insert Into decklists ("GEM ID", Copies, Card, "Event Name", pitch) Values (?,?,?,?,?)"""
    cnxn = sqlite3.connect(DATABASE)
    cursor = cnxn.cursor()

    for card in player.cards:
        cursor.execute(insert_sql, tuple((player.gem_id, card.copies, card.card_name, event_url_name, card.pitch)))
    
    cursor.close()
    cnxn.commit()

def post_pairings_to_sql(event):
    insert_sql = """Insert Into pairings (Event, Round, "Table", Seat, "Gem ID", Outcome, tbl_id) Values (?,?,?,?,?,?,?)"""
    cnxn = sqlite3.connect(DATABASE)
    cursor = cnxn.cursor()

    for seat in event.pairings:
        payload = astuple(seat) + tuple((seat.table_id, ))
        cursor.execute(insert_sql, payload)
    
    cursor.close()
    cnxn.commit()

def post_players_to_sql(event):
    insert_sql = """Insert Into participants ("Gem ID", "Name", "Event Date", "Format", "Hero", "Event Name") Values (?,?,?,?,?,?)"""
    cnxn = sqlite3.connect(DATABASE)
    cursor = cnxn.cursor()

    for player in event.players:
        payload = tuple((player.gem_id, player.player_name, player.event_date, player.format, player.hero, event.url_name))
        cursor.execute(insert_sql, payload)

    cursor.close()
    cnxn.commit()

def export_sql_to_csv():
    sql_select = {"tournament_lists": """Select gem_id, url_name, hero, card, copies From tournament_lists""", "results":"""Select url_name, round, gem_id, hero, opponent, outcome, table_id From results"""}

    cnxn = sqlite3.connect(DATABASE)
    cursor = cnxn.cursor()

    for results_name, statement in sql_select.items():
        cursor.execute(statement)
        dataset = cursor.fetchall()

        with open(f"{results_name}.csv", "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow([header[0] for header in cursor.description])
            writer.writerows(dataset)

    cursor.close()

# %%
all_events = event_entry()
post_events_to_sql(all_events)

for event in all_events:
    get_pairings(event)
    get_player_info(event)
    print(f"Iterating through {event.display_name}'s players")
    for player in event.players:
        add_card_to_player(player)
        post_cards_to_sql(player, event.url_name)
    print(f"Done adding cards to SQL for {event.display_name}")

    post_pairings_to_sql(event)
    post_players_to_sql(event)
    print(f"Done posting pairings and players to SQL for {event.display_name}")

export_sql_to_csv()
print("Job Done")