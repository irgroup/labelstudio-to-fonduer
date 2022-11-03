# -*- coding: utf-8 -*-
"""Helpfull tools to use fonduer."""

import sqlalchemy


def save_create_project(conn_string: str, project_name: str):
    """Cleanup the Fonduer database and create a new project in the database.

    Args:
        conn_string (str): Fonduer postgres connection string.
        project_name (str): Fonduer project name.
    """
    # create connection
    engine = sqlalchemy.create_engine(conn_string)
    conn = engine.connect()
    conn.execute("commit")

    # Check existing projects
    current_dbs = engine.execute("SELECT datname FROM pg_database;").fetchall()
    current_dbs = [db[0] for db in current_dbs]

    # Wipe if project exists
    if project_name in current_dbs:
        engine = sqlalchemy.create_engine(conn_string)
        conn = engine.connect()
        conn.execute("commit")
        conn.execute(
            f"""SELECT 
            pg_terminate_backend(pid) 
        FROM 
            pg_stat_activity 
        WHERE 
            -- don't kill my own connection!
            pid <> pg_backend_pid()
            -- don't kill the connections to other databases
            AND datname = '{project_name}'
            ;"""
        )

        conn.execute("commit")
        conn.execute("drop database " + project_name)

    # Create Project
    conn.execute("commit")
    conn.execute("create database " + project_name)
    conn.close()
