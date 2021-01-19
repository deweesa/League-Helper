from key import API_KEY, DB_PATH
import requests 
import sqlite3
import json
import time

TIMED_OUT = False

def main():
   createTables()
   buildSummoner()
   buildMatchHistory()

#Creates table if they do not exist
def createTables():
    conn = sqlite3.connect("D:\\Projects\\League-Helper\\tables.db")

    #create summoner table 
    conn.execute("""CREATE TABLE IF NOT EXISTS summoner
		      (accountId text primary key, profileIconId integer, revisionDate integer, summonerName text, id text, puuid text, summonerLevel integer)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS match
               (gameId integer, summonerName text, win integer, champion integer, role text, lane text, seasonId integer, gameVersion text)""")
    
    conn.close()


def statCodeHelper(status_code, func, param):
    global TIMED_OUT

    if status_code == 429 and TIMED_OUT is False:
        print("Sleeping for first time out warning")
        time.sleep(1)
        TIMED_OUT = True
        return func(param)
    elif status_code == 429 and TIMED_OUT is True:
        print("Sleeping for second timeout warning")
        time.sleep(140)
        TIMED_OUT = False
        return func(param)
    elif status_code == 429:
        print("there is a bug in the statCodeHelper")
        time.sleep(30)
        return func(param)
    elif status_code is 400:
        print("Bad Request")


def summoner(summonerName: str) -> json:
    req = requests.get('https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-name/' + summonerName, params=API_KEY)

    if req.status_code != 200:
       return statCodeHelper(req.status_code, summoner, summonerName)

    return req.json()

def matchBySummoner(encryptedAccountId:str, beginIndex:int = 0) -> json:
    params = {}
    params['api_key'] = API_KEY['api_key']
    params['beginIndex'] = beginIndex
    req = requests.get('https://na1.api.riotgames.com/lol/match/v4/matchlists/by-account/' + encryptedAccountId, params=params)
    
    statCodeHelper(req.status_code, matchBySummoner, encryptedAccountId)

    return req.json()

def matchByMatchId(matchId: int) -> json:
    req = requests.get('https://na1.api.riotgames.com/lol/match/v4/matches/' + str(matchId), params=API_KEY)

    statCodeHelper(req.status_code, matchByMatchId, matchId)

    return req.json()


def buildSummoner():
    #list of current gamers
    gamers = ["Amon Byrne", "BluffMountain", "BluffMountain72", "FocusK", "ForeseenBison", "Moisturiser", "Pasttugboat", "stumblzzz", "JasaD15"]
    conn = sqlite3.connect(DB_PATH)    
    curr = conn.cursor()

    #Checking for each gamer
    for gamer in gamers:
        response = summoner(gamer)
        gamer_info = (response["accountId"], response["profileIconId"], response["revisionDate"], response["name"], response["id"], response["puuid"], response["summonerLevel"])

        curr.execute("select * from summoner where accountId = ?", [gamer_info[0]])

        #if the fetch from the above query is empty, then the Player and their info is not in the table
        if curr.fetchone() is None:
            curr.execute('INSERT INTO summoner VALUES (?,?,?,?,?,?,?)', gamer_info)
            conn.commit()
        else:
            print(gamer_info[3] + " is already in the table")
    
    conn.close()


def getParticipantId(participantIds: [json], accountId: str) -> int:
    for particpant in participantIds:
        if particpant['player']['accountId'] == accountId:
            return particpant['participantId']
    
    return -1


def getWin(participants: [json], participantId: int) -> int:
    for participant in participants:
        if participant['participantId'] == participantId:
            if participant['stats']['win']:
                return 1
            else:
                return 0

    return -1


def buildMatchHistory():
    conn = sqlite3.connect(DB_PATH)
    curr = conn.cursor()

    curr.execute("select accountId, summonerName from summoner;")

    query_result = curr.fetchall()
    for row in query_result:
        accountId = row[0]
        summonerName = row[1]

        matchListDto = matchBySummoner(accountId)

        beginIndex = 100
        while(matchListDto["matches"] != []):
            #print(response["matches"])
            print(matchListDto)
            
            
            #Get all the matches for one player
            matchList = matchListDto['matches']

            #For every match the player has played get the detailed stats
            for match in matchList:
                #Probably safe to assume that for our group any game played is played together, ie a win for one is a win for all
                #but I think it's better to avoid that logic keep it general
                if match['queue'] != 400:
                    print("Not a 5v5 Draft game, skipping table insertion\n\tSummoner: %s", summonerName)
                    continue
                
                matchId = match['gameId']
                matchDto = matchByMatchId(matchId)
                print(matchDto)
                seasonId = matchDto['seasonId']
                gameVersion = matchDto['gameVersion']

                participantId = getParticipantId(matchDto['participantIdentities'], accountId)
                win = getWin(matchDto['participants'], participantId)

                champion = match['champion']
                role = match['role']
                lane = match['lane']

                # curr.execute("insert into match values gameId=:gameId, summonerName=:summonerName, win=:win, champion=:champion, role=:role, lane=:lane, seasonId=:seasonId, gameVersion=:gameVersion", 
                #               {"gameId": matchId, "summonerName": summonerName, "win": win, "champion": champion, "role": role, "lane": lane, "seasonId": seasonId, "gameVersion": gameVersion})

                data_tuple = (matchId, summonerName, win, champion, role, lane, seasonId, gameVersion)
                curr.execute("insert into match (gameId, summonerName, win, champion, role, lane, seasonId, gameVersion) values (?,?,?,?,?,?,?,?)", data_tuple)

            matchListDto = matchBySummoner(accountId, beginIndex)
            beginIndex += 100

    conn.close()   


if __name__=="__main__":
    main()
    