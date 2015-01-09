#!/usr/bin/env python


import sqlite3
import sys


con = sqlite3.connect('servers.db')

with con:
    
    cur = con.cursor()    
    cur.execute("DROP TABLE IF EXISTS users")
    cur.execute("DROP TABLE IF EXISTS servers")
    cur.execute("CREATE TABLE users(user_id INTEGER PRIMARY KEY, email TEXT, host TEXT, port INT, request TEXT, confirmation TEXT)")
    cur.execute("CREATE TABLE servers(server_id INTEGER PRIMARY KEY, name TEXT, host TEXT, port INT)")
 
#    cur.execute("INSERT INTO servers (name, host, port) VALUES('etb1', 'localhost', 8085)")
#    cur.execute("INSERT INTO servers  (name, host, port) VALUES('etb2', 'localhost', 8086)")
    


