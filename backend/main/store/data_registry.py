#
# This file is the interface between the stores and the database
#

import sqlite3
from sqlite3 import Connection

from typing import Set, List, Optional

from backend.main.objects.candidate import Candidate
from backend.main.objects.voter import Voter, VoterStatus, obfuscate_national_id, decrypt_name
from backend.main.objects.ballot import Ballot
from backend.main.detection.pii_detection import redact_free_text


class VotingStore:
    """
    A singleton class that encapsulates the interface between the stores and the databases.

    To use, simply do:

    >>> voting_store = VotingStore.get_instance()   # this will create the stores, if they haven't been created
    >>> voting_store.add_candidate(...)  # now, you can call methods that you need here
    """

    voting_store_instance = None

    @staticmethod
    def get_instance():
        if not VotingStore.voting_store_instance:
            VotingStore.voting_store_instance = VotingStore()

        return VotingStore.voting_store_instance

    @staticmethod
    def refresh_instance():
        """
        DO NOT MODIFY THIS METHOD
        Only to be used for testing. This will only work if the sqlite connection is :memory:
        """
        if VotingStore.voting_store_instance:
            VotingStore.voting_store_instance.connection.close()
        VotingStore.voting_store_instance = VotingStore()

    def __init__(self):
        """
        DO NOT MODIFY THIS METHOD
        DO NOT call this method directly - instead use the VotingStore.get_instance method above.
        """
        self.connection = VotingStore._get_sqlite_connection()
        self.create_tables()

    @staticmethod
    def _get_sqlite_connection() -> Connection:
        """
        DO NOT MODIFY THIS METHOD
        """
        return sqlite3.connect(":memory:", check_same_thread=False)

    def create_tables(self):
        """
        Creates Tables
        """
        self.connection.execute(
            """CREATE TABLE candidates (candidate_id integer primary key autoincrement, name text)""")
        self.connection.execute(
            """CREATE TABLE voters (obfuscated_national_id string primary key, obfuscated_first_name text NOT NULL, obfuscated_last_name text NOT NULL)""")
        self.connection.execute(
            """CREATE TABLE voter_status (obfuscated_national_id string primary key, status string)""")
        self.connection.execute(
            """CREATE TABLE ballots (obfuscated_national_id string, ballot_number string, chosen_candidate_id string, voter_comments text, valid boolean, primary key (obfuscated_national_id, ballot_number))""")
        self.connection.commit()

    def add_candidate(self, candidate_name: str):
        """
        Adds a candidate into the candidate table, overwriting an existing entry if one exists
        """
        self.connection.execute(
            """INSERT INTO candidates (name) VALUES (?)""", (candidate_name, ))
        self.connection.commit()

    def get_candidate(self, candidate_id: str) -> Candidate:
        """
        Returns the candidate specified, if that candidate is registered. Otherwise returns None.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT * FROM candidates WHERE candidate_id=?""", (candidate_id,))
        candidate_row = cursor.fetchone()
        candidate = Candidate(
            str(candidate_id), candidate_row[1]) if candidate_row else None
        self.connection.commit()

        return candidate

    def get_all_candidates(self) -> List[Candidate]:
        """
        Gets ALL the candidates from the database
        """
        cursor = self.connection.cursor()
        cursor.execute("""SELECT * FROM candidates""")
        all_candidate_rows = cursor.fetchall()
        all_candidates = [Candidate(str(candidate_row[0]), candidate_row[1])
                          for candidate_row in all_candidate_rows]
        self.connection.commit()

        return all_candidates

    def add_voter(self, voter: Voter) -> bool:
        """Adds a voter to the voters table"""
        if self.get_voter_status(voter.national_id) != VoterStatus.NOT_REGISTERED:
            return False

        minimal_voter = voter.get_minimal_voter()

        self.connection.execute(
            """INSERT INTO voters (obfuscated_national_id, obfuscated_first_name, obfuscated_last_name) VALUES (?, ?, ?)""", (minimal_voter.obfuscated_national_id, minimal_voter.obfuscated_first_name, minimal_voter.obfuscated_last_name, ))
        self.connection.execute(
            """INSERT INTO voter_status (obfuscated_national_id, status) VALUES (?, ?)""", (minimal_voter.obfuscated_national_id, VoterStatus.REGISTERED_NOT_VOTED.value, ))
        self.connection.commit()

        return True

    def get_voter_status(self, voter_national_id) -> VoterStatus:
        """Gets the voters status from the voter_status table"""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT * FROM voter_status WHERE obfuscated_national_id=?""", (obfuscate_national_id(voter_national_id),))
        voter_row = cursor.fetchone()

        if voter_row == None:
            return VoterStatus.NOT_REGISTERED

        return VoterStatus(voter_row[1])

    def set_voter_status(self, voter_national_id, status: VoterStatus):
        cursor = self.connection.cursor()
        cursor.execute(
            """UPDATE voter_status SET status = ? WHERE obfuscated_national_id = ?""", (status.value, obfuscate_national_id(voter_national_id), ))
        self.connection.commit()

    def get_voter_names(self, voter_national_id) -> List[str]:
        """Gets the voters unobfuscated names"""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT obfuscated_first_name, obfuscated_last_name FROM voters WHERE obfuscated_national_id=?""", (obfuscate_national_id(voter_national_id),))
        voter_row = cursor.fetchone()

        return [decrypt_name(voter_row[0]), decrypt_name(voter_row[1])]

    def delete_voter(self, voter_national_id):
        """Delete a voter identified by national id"""
        cursor = self.connection.cursor()
        cursor.execute(
            """DELETE from voters where obfuscated_national_id = ?""", (obfuscate_national_id(voter_national_id),))
        cursor.execute(
            """DELETE from voter_status where obfuscated_national_id = ?""", (obfuscate_national_id(voter_national_id),))
        self.connection.commit()

    def add_ballot_to_voter(self, voter_national_id, ballot_number):
        """Assign the ballot to a voter identified by national id"""
        self.connection.execute(
            """INSERT INTO ballots (obfuscated_national_id, ballot_number, valid) VALUES (?, ?, true)""", (obfuscate_national_id(voter_national_id), ballot_number))
        self.connection.commit()

    def get_ballot(self, ballot_number) -> Optional[Ballot]:
        """Get the ballot by ballot_number"""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT ballot_number, chosen_candidate_id, voter_comments FROM ballots WHERE ballot_number=? AND valid = true""", (ballot_number,))
        ballot_row = cursor.fetchone()

        if ballot_row == None:
            return None

        return Ballot(ballot_row[0], ballot_row[1], ballot_row[2])

    def get_ballot_for_voter(self, ballot_number, voter_national_id) -> Optional[Ballot]:
        """Get the ballot for the given national id"""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT ballot_number, chosen_candidate_id, voter_comments FROM ballots WHERE ballot_number = ? AND obfuscated_national_id = ? AND valid = true""", (ballot_number, obfuscate_national_id(voter_national_id),))
        ballot_row = cursor.fetchone()

        if ballot_row == None:
            return None

        return Ballot(ballot_row[0], ballot_row[1], ballot_row[2])

    def count_ballot_for_voter(self, ballot: Ballot, voter_national_id: str):
        """Count the given ballot for the given national id"""
        names = self.get_voter_names(voter_national_id)

        cursor = self.connection.cursor()
        cursor.execute(
            """UPDATE voter_status SET status = ? WHERE obfuscated_national_id = ?""", (VoterStatus.BALLOT_COUNTED.value, obfuscate_national_id(voter_national_id), ))

        cursor.execute(
            """UPDATE ballots SET chosen_candidate_id = ?, voter_comments = ? WHERE ballot_number = ? AND obfuscated_national_id = ?""", (ballot.chosen_candidate_id, redact_free_text(ballot.voter_comments, names), ballot.ballot_number, obfuscate_national_id(voter_national_id), ))

        cursor.execute(
            """UPDATE ballots SET valid = false WHERE ballot_number <> ? AND obfuscated_national_id = ?""", (ballot.ballot_number, obfuscate_national_id(voter_national_id), ))
        self.connection.commit()

    def get_winner(self) -> Candidate:
        """Determine the winning candidate of the election"""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT chosen_candidate_id, count(*) as votes FROM ballots WHERE valid = true AND chosen_candidate_id IS NOT NULL GROUP BY chosen_candidate_id ORDER BY votes desc""")
        winner_row = cursor.fetchone()

        winner_id = winner_row[0]
        return self.get_candidate(str(winner_id))

    def get_all_ballot_comments(self) -> Set[str]:
        """Get all ballot comments and return them in a string set."""
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT voter_comments FROM ballots WHERE voter_comments IS NOT NULL AND voter_comments <> ''""")
        rows = cursor.fetchall()
        return {row[0] for row in rows}

    def get_all_fraudulent_voters(self) -> List[Voter]:
        """
        Return a list of fraudulent voters.
        Please NOTE that voter national ids are of course obfuscated.
        """
        cursor = self.connection.cursor()
        cursor.execute(
            """SELECT 
              v.obfuscated_national_id, v.obfuscated_first_name, v.obfuscated_last_name, s.status
            FROM voters v, voter_status s 
            WHERE v.obfuscated_national_id = s.obfuscated_national_id 
            AND s.status = ?""", (VoterStatus.FRAUD_COMMITTED.value,))
        rows = cursor.fetchall()

        return [Voter(decrypt_name(row[1]), decrypt_name(row[2]), row[0]) for row in rows]

    def invalidate_ballot(self, ballot_number) -> bool:
        cursor = self.connection.cursor()

        cursor.execute(
            """UPDATE ballots SET valid=false WHERE ballot_number = ? AND chosen_candidate_id IS NULL AND valid=true""", (ballot_number,))
        updated_rows = cursor.rowcount
        self.connection.commit()

        if updated_rows == 1:
            return True
        else:
            return False
