from key import API_KEY
import requests 
import sqlite3

def main():
   createTables()

def createTables():
    conn = sqlite3.connect("D:\\Projects\\League-Helper\\tables.db")
    cur = conn.cursor()

    #create summoner table 
    cur.execute("""CREATE TABLE IF NOT EXISTS summoner
		      (accountId text, profileIconId integer, revisionDate integer, summonerName text, id text, puuid text, summonerLevel integer)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS match
              (gameId integer, role)""")
if __name__=="__main__":
    main()