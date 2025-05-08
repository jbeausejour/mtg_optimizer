import csv
import os
import asyncio
from sqlalchemy import text, inspect
from app.utils.async_context_manager import flask_session_scope

from app.models.site import Site
from app.models.user_buylist_card import UserBuylistCard

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "..", "data")

SITE_LIST_FILE = os.path.join(DATA_DIR, "site_list.txt")
CARD_LIST_FILE = os.path.join(DATA_DIR, "card_list.txt")
SQL_FILE = os.path.join(DATA_DIR, "sql", "magic_sets.sql")


async def truncate_tables():
    async with flask_session_scope() as session:
        await session.execute(text("DELETE FROM site"))
        await session.execute(text("DELETE FROM user_buylist_card"))


async def load_site_list():
    async with flask_session_scope() as session:
        with open(SITE_LIST_FILE, "r") as file:
            csv_reader = csv.reader(file)
            headers = next(csv_reader)
            column_indices = {column.strip().lower(): index for index, column in enumerate(headers)}

            for row in csv_reader:
                await Site.create(
                    session,
                    **{
                        "name": row[column_indices["name"]].strip(),
                        "url": row[column_indices["url"]].strip(),
                        "method": row[column_indices["method"]].strip(),
                        "active": row[column_indices["active"]].strip().lower() == "yes",
                        "country": row[column_indices["country"]].strip(),
                        "type": row[column_indices["type"]].strip(),
                    },
                )


async def load_card_list():
    async with flask_session_scope() as session:
        with open(CARD_LIST_FILE, "r") as file:
            lines = file.readlines()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            quantity, card_name = line.split(" ", 1)
            quantity = int(quantity.strip())
            card_name = card_name.strip()

            await UserBuylistCard.create(
                session,
                **{
                    "name": card_name,
                    "quantity": quantity,
                },
            )


async def load_sql_file():
    with open(SQL_FILE, "r") as file:
        sql_commands = file.read().split(";")

    async with flask_session_scope() as session:
        for command in sql_commands:
            command = command.strip()
            if command:
                try:
                    await session.execute(text(command))
                except Exception as e:
                    print(f"Error executing command: {command}\n{e}")


async def load_all_data():
    await load_site_list()
    await load_card_list()
    # await load_sql_file()


if __name__ == "__main__":
    asyncio.run(truncate_tables())
    asyncio.run(load_all_data())
    print("Data loaded successfully.")
