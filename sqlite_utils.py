import sqlite3
import os
import pandas as pd
from pandas import Series, DataFrame


def get_sqlite_db_path():
    root_path = os.path.abspath(".")

    # whether .db has directory
    db_path = os.path.join(root_path, ".db")
    if not os.path.isdir(db_path):
        os.mkdir(db_path)

    # whether .sqlite has directory
    sqlite_path = os.path.join(db_path, ".sqlite")
    if not os.path.isdir(sqlite_path):
        os.mkdir(sqlite_path)

    return sqlite_path


class SQLiteDB:
    def __init__(self, name):
        # name and db path
        self.name = name
        self.path = os.path.join(get_sqlite_db_path(), f"{self.name}.db")

        # connection
        self.connection = None
        # cursor
        self.cursor = None

    def connect(self):
        self.connection = sqlite3.connect(self.path)
        self.cursor = self.connection.cursor()
        return

    def disconnect(self):
        self.connection.close()
        return

    def execute(self, sql: str, *args):
        self.cursor.execute(sql, args)
        return

    def fetch_one(self):
        return self.cursor.fetchone()

    def fetch_all(self):
        return self.cursor.fetchall()

    def reset_cursor(self):
        self.cursor.close()
        self.cursor = self.connection.cursor()
        return

    def commit(self):
        self.connection.commit()
        return

    """pandas DataFrame interface"""

    def pd_to_sql(self, df: DataFrame, table_name: str, if_exists: str = "fail"):
        df.to_sql(table_name, self.connection, if_exists=if_exists)
        return

    def pd_read_sql(self, sql):
        return pd.read_sql(sql, self.connection, index_col="index")
