# %%
import pandas as pd
import requests
import sqlite3
import re
from pathlib import Path
from bs4 import BeautifulSoup

# %%
# nit: Generally, module level constants are UPPERCASE. https://peps.python.org/pep-0008/#constants
database = "fab_world_tour.db"

# Consider using a dataclasses.dataclass instead to eliminate some boilerplate
# Partial example of event as a dataclass. The import should be at the top, but it's here to collocate the changes
import dataclasses

@dataclasses.dataclass
class Event:
    """A Flesh and Blood tournament."""
    name: str
    display_name: str
    draft_rounds: int
    draft_rounds_start: int | None
    draft_rounds_end: int | None
    rounds_total: int

    @property
    def constructed_rounds(self) -> list[int]:
        ...


class Event:
    def __init__(self, name, display_name, draft_rounds, rounds_total, draft_rounds_start, draft_rounds_end):
        self.name = name
        self.display_name = display_name
        self.draft_rounds = draft_rounds
        self.draft_rounds_start = draft_rounds_start
        self.draft_rounds_end = draft_rounds_end
        self.rounds_total = rounds_total

        if self.draft_rounds:
            # This could be more readable:
            # 1. Use the start and stop arguments to `range()` instead of adding one to it's output (`number + 1`). This is somewhat personal preference,
            #    but I'd argue it communicates intent ("give me these sequential numbers") more clearly. It also lets you drop the `number + 1` from the comparison.
            # 2. Do not combine `not` with comparison operators. Re-write the filter so that it can be framed positively (i.e. `if <expression>`).
            #    If you prefer the `not <expression>` form, then convert the comparison to a function with clear name, e.g. `in_draft_rounds()` or `between(start, end)`
            #    so that the intent of the filter can be understood quickly.
            self.constructed_rounds = [number + 1 for number in range(self.rounds_total) if not self.draft_rounds_start <= number + 1 <= self.draft_rounds_end]
        else:
            self.constructed_rounds = [number + 1 for number in range(self.rounds_total)]
        
        # If draft_rounds_start and draft_rounds_end were coallecsed to `0`, then the above branching could be eliminated. Something like this:
        draft_rounds_start = draft_rounds_start or 0
        draft_rounds_end = draft_rounds_end or 0
        # I don't love the name `draft_rounds_set`, but `draft_rounds` was already taken and I'm not being paid enough to spend time on naming ;)
        draft_rounds_set = set(range(draft_rounds_start, draft_rounds_end + 1))  # This will be `{0}` if there are no draft rounds
        # Or as a comphrension
        draft_rounds_set = {__ for __ in range(draft_rounds_start, draft_rounds_end + 1)}
        self.constructed_rounds = [round_ for round_ in range(1, self.rounds_total + 1) if round_ not in draft_rounds_set]


    def show(self):
        # This is fine as is if this is the format you want, but you could use [pprint](https://docs.python.org/3/library/pprint.html#module-pprint).
        # If you use a dataclass, then you get something like this via the provided __repr__ for "free"
        inst_var = vars(self)
        for name, value in inst_var.items():
            print(f"{name}: {value}")

# %%
def direct_entry_event_creation():
    output = []

    events_being_added = user_input_int("How Many Events Are Being Added? ")

    # ubernit: Generally, if a variable is not going to be used, then it's named `__` to indicate it's intentionally not used.
    for __ in range(events_being_added):
        # Interactively asking your user for input is totally fine if that's the interface you want to provide.
        # However, if this was my project, I'd consider presenting this as a command line tool and use
        # something like [`argparse`](https://docs.python.org/3/library/argparse.html), [`docopt`](https://pypi.org/project/docopt/),
        # or [`click`](https://pypi.org/project/click/) to help with input validation.
        event_name = input("Event name found in the URL: ")
        display_name = input("Event name to be shown: ")
        rounds_total = user_input_int("# of rounds at the Event: ")
        draft_rounds = user_input_bool("Rounds of draft (True/False): ")

        if draft_rounds:
            draft_rounds_start = user_input_int("First round of draft: ")
            draft_rounds_end = user_input_int("Last round of draft: ")
        else:
            draft_rounds_start = None  # Consider setting 0 instead
            draft_rounds_end = None

        event = Event(
            # Generally there's no spacing between a parameter name and the argument when calling a function.
            # I do not recommend manually fixing this, but I do recommend finding and using a formatter. E.g. https://docs.astral.sh/ruff/formatter/
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

    # It's been a long time since I've used Pandas, but
    # I'd be surprised if there's not a more efficient way to do this.
    # Something like `for row in df.itertuples(index=False):`
    # See https://towardsdatascience.com/efficiently-iterating-over-rows-in-a-pandas-dataframe-7dd5f9992c01/
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
        # This level of validation is probably fine for this project,
        # but it did give me pause that "Turduckin" would be considered valid.
        valid_input = user_input.startswith(("t","f"))

    return user_input.startswith("t")

# Instead of checking for a numeric string, check for a string that can be converted to an int.
# There are lots of numeric strings that cannot become ints, e.g. ⅕.
def user_input_int(prompt):
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            # Invalid input. Could print a nice message to the user.
            pass

def choose_bulk_direct():
    valid_input = False

    while not valid_input:
        user_input = input("1. Bulk Entry\n2. Direct Entry")
        # This could be simpler by checking for presence instead of absence.
        if user_input in ['1','2']:
            return user_input == '1'
        # Again, this could output an error message to the user.
            
        
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
            # This is fine as is, but this could use the integer division operator (`//`) instead
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

def make_player_list(pairings):
    output = []

    # This is O(n^2) because of the deduplication check. This is probably fine in practice
    # for this use case, but it could be be O(n) if output was a set.
    for record in pairings:
        # This would be much more readable as `record.gem_id`. See comment above in `get_pairings`
        # about using a self documenting data structure.
        if record[4] not in output and record[4]:
            output.append(record[4])

    return output

def get_decklist(event, player_list):
    output = []
    coverage_url = "https://fabtcg.com/en/coverage/{}/decklist/{}/"

    # `id` is a built-in
    for id_ in player_list:
        decklist_url = coverage_url.format(event, id_)

        page = requests.get(decklist_url)
        soup = BeautifulSoup(page.text, "html")

        if page.status_code == 200:
            output.append([data.text.strip() for data in soup.find_all("td")])
        else:
            output.append([id_, "Unknown", None, None, None, "Unknown"])

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


