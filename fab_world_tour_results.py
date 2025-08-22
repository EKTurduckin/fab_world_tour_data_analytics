# %%
import pandas as pd
import requests
import sqlite3
import re
from pathlib import Path
from bs4 import BeautifulSoup

# %%
database = "fab_world_tour.db"

class Event:
    def __init__(self, name, display_name, draft_rounds, rounds_total, draft_rounds_start, draft_rounds_end):
        self.name = name
        self.display_name = display_name
        self.draft_rounds = draft_rounds
        self.draft_rounds_start = draft_rounds_start
        self.draft_rounds_end = draft_rounds_end
        self.rounds_total = rounds_total

        if self.draft_rounds:
            self.constructed_rounds = [number + 1 for number in range(self.rounds_total) if not self.draft_rounds_start <= number + 1 <= self.draft_rounds_end]
        else:
            self.constructed_rounds = [number + 1 for number in range(self.rounds_total)]

    def show(self):
        inst_var = vars(self)
        for name, value in inst_var.items():
            print(f"{name}: {value}")

# %%
def direct_entry_event_creation():
    output = []

    events_being_added = user_input_int("How Many Events Are Being Added? ")

    for i in range(events_being_added):
        event_name = input("Event name found in the URL: ")
        display_name = input("Event name to be shown: ")
        rounds_total = user_input_int("# of rounds at the Event: ")
        draft_rounds = user_input_bool("Rounds of draft (True/False): ")

        if draft_rounds:
            draft_rounds_start = user_input_int("First round of draft: ")
            draft_rounds_end = user_input_int("Last round of draft: ")
        else:
            draft_rounds_start = None
            draft_rounds_end = None

        event = Event(
            name = event_name,
            display_name = display_name,
            draft_rounds = draft_rounds,
            rounds_total = rounds_total,
            draft_rounds_start = draft_rounds_start,
            draft_rounds_end = draft_rounds_end
            )
    
        output.append(event)

    return output

def bulk_entry_event_creation(csv_path):
    output = []
    csv_path = Path(csv_path)

    df = pd.read_csv(csv_path)

    for i in range(len(df)):
        event_name = df.loc[[i], "url_name"].item()
        display_name = df.loc[[i], "display_name"].item()
        rounds_total = df.loc[[i], "rounds_total"].item()
        draft_rounds = df.loc[[i], "draft_rounds"].item()

        if draft_rounds:
            draft_rounds_start = df.loc[[i], "draft_rounds_start"].item()
            draft_rounds_end = df.loc[[i], "draft_rounds_end"].item()
        else:
            draft_rounds_start = None
            draft_rounds_end = None

        event = Event(
            name = event_name,
            display_name = display_name,
            draft_rounds = draft_rounds,
            rounds_total = rounds_total,
            draft_rounds_start = draft_rounds_start,
            draft_rounds_end = draft_rounds_end
            )
    
        output.append(event)

    return output
    
def user_input_bool(prompt):
    valid_input = False

    while not valid_input:
        user_input = input(prompt).lower()
        valid_input = user_input.startswith(("t","f"))

    return user_input.startswith("t")

def user_input_int(prompt):
    valid_input = False

    while not valid_input:
        user_input = input(prompt)
        valid_input = user_input.isnumeric()

    return int(user_input)            

def choose_bulk_direct():
    valid_input = False

    while not valid_input:
        user_input = input("1. Bulk Entry\n2. Direct Entry")
        
        if user_input not in ['1','2']:
            valid_input = False
        else:
            valid_input = True
            return user_input.startswith('1')
        
def get_pairings(event, constructed_rounds):
    output = []
    url = "https://fabtcg.com/en/coverage/{}/results/{}/"

    for round in constructed_rounds:
        page = requests.get(url.format(event, round))
        soup = BeautifulSoup(page.text, "html")

        player = soup.find_all("div", {"class":"tournament-coverage__player-hero-and-deck"})
        winner = soup.find_all("div", {"class":"tournament-coverage__result"})

        for idx, id in enumerate(player):
            table = int(idx / 2) + 1

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

            record = [event, round, table, seat, gem_id, player_status]

            output.append(record)

    return output

def make_player_list(pairings):
    output = []

    for record in pairings:
        if record[4] not in output and record[4]:
            output.append(record[4])

    return output

def get_decklist(event, player_list):
    output = []
    coverage_url = "https://fabtcg.com/en/coverage/{}/decklist/{}/"

    for id in player_list:
        decklist_url = coverage_url.format(event, id)

        page = requests.get(decklist_url)
        soup = BeautifulSoup(page.text, "html")

        if page.status_code == 200:
            output.append([data.text.strip() for data in soup.find_all("td")])
        else:
            output.append([id, "Unknown", None, None, None, "Unknown"])

    return output

def decklist_to_df(event, decklists):
    decklists = pd.DataFrame.from_records(decklists)
    decklists.index = [re.search(r"(\d+)", name).group(1) for name in decklists[0]]

    participants = decklists.iloc[:,0:5].copy()
    participants = participants.drop(2, axis=1)
    participants = participants.rename(columns={0:"Name", 1:"Event Date", 3:"Format", 4:"Hero"})
    participants["Event Name"] = event

    participants.index.rename("Gem ID", inplace=True) 

    decklists = decklists.drop([0,1,2,3,4], axis=1)

    decklists = pd.melt(decklists, ignore_index=False, value_name="import name")["import name"].to_frame()

    decklists[["Copies","Card"]] = decklists["import name"].str.split(" x ", expand=True)
    decklists = decklists.drop("import name", axis=1).dropna()

    decklists.index.rename("Gem ID", inplace=True)
    decklists["Event Name"] = event

    return participants, decklists

def df_to_sql(dataframe, sql_table_name, index=True):
    connection = sqlite3.connect(database)

    dataframe.to_sql(sql_table_name, connection, if_exists="append", index=index)

# %%
if choose_bulk_direct():
    events = bulk_entry_event_creation("events.csv")
else:
    events = direct_entry_event_creation()

for event in events[1:]:
    print(event.display_name)
    pairings = get_pairings(event.name, event.constructed_rounds)
    player_list = make_player_list(pairings)
    decklists = get_decklist(event.name, player_list)
    tournament = decklist_to_df(event.name, decklists)
    participant_df = tournament[0]
    decklist_df = tournament[1]
    pairings_df = pd.DataFrame.from_records(pairings, columns=["Event", "Round","Table","Seat","Gem ID","Outcome"])
    event_name_df = pd.DataFrame.from_records([[event.name, event.display_name]],columns=["event_url_portion", "event_name"])
    

    df_to_sql(participant_df, "participants")
    df_to_sql(decklist_df, "decklists")
    df_to_sql(pairings_df, "pairings", False)
    df_to_sql(event_name_df, "events", False)

# %%
# Tableau public doesn't like SQL connections, so until then I need to export to an xlsx.
# And turns out I'm trying to add too many rows to an xlsx, so CSV we go.
cnxn = sqlite3.connect(database)
csv_results = pd.read_sql("Select * From csv_output", cnxn)

csv_results.to_csv("World Tour Results 2025.csv", index=False)


