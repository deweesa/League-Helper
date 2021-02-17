from key import API_KEY, DB_PATH
import requests 
import sqlite3
import json
import time

TIMED_OUT = False

def main():
   createTables()
   buildSummoner()
   updateMatchHistory()

#Creates table if they do not exist
def createTables():
    conn = sqlite3.connect("D:\\Projects\\League-Helper\\tables.db")

    #create summoner table 
    conn.execute("""CREATE TABLE IF NOT EXISTS summoner
		      (accountId text primary key, profileIconId integer, revisionDate integer, summonerName text, id text, puuid text, summonerLevel integer)""")

    conn.execute("""CREATE TABLE IF NOT EXISTS match
               (gameId integer, summonerName text, win integer, champion integer, role text, lane text, queue integer, seasonId integer, timestamp integer, gameVersion text)""")
    
    conn.commit()
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
        print("\tout of timeout")
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
    
    if req.status_code != 200:
        return statCodeHelper(req.status_code, matchBySummoner, encryptedAccountId)

    return req.json()

def matchByMatchId(matchId: int) -> json:
    req = requests.get('https://na1.api.riotgames.com/lol/match/v4/matches/' + str(matchId), params=API_KEY)

    if req.status_code != 200:
        return statCodeHelper(req.status_code, matchByMatchId, matchId)

    return req.json()


def buildSummoner():
    #list of current gamers
    gamers = ["Amon Byrne", "BluffMountain", "BluffMountain72", "FocusK", "ForeseenBison", "Moisturiser", "Pasttugboat", "stumblzzz", "JasaD15"]
    conn = sqlite3.connect(DB_PATH)    
    curr = conn.cursor()

    #Checking for each gamer
    for gamer in gamers:
        print(gamer)
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

#TODO:
# x Check to see if the game was a custom, playerDto from participants will be empty if that is the case
def updateMatchHistory():
    #connect to the db and create the cursor
    conn = sqlite3.connect(DB_PATH)
    curr = conn.cursor()
    inserted = 0
    #get the timestamp for the most recent game, if the table is empty then timestamp is 0
    curr.execute("select coalesce(max(timestamp),0) from match;")
    min_timestamp = curr.fetchone()[0]

    #get the accoutnId and summoner name from summoner table
    curr.execute("select accountId, summonerName from summoner;")

    query_result = curr.fetchall()
    for row in query_result:
        accountId = row[0]
        summonerName = row[1]
        print('inserting for ' + summonerName)

        matchListDto = matchBySummoner(accountId)
        matchList = matchListDto["matches"]

        oldFound = False

        beginIndex = 100
        while(matchList != []):
            #For every match the player has played get the detailed stats
            for match in matchList:
                timestamp = match['timestamp']
                #I think this is working but need to shift it up to the first check
                if(timestamp <= min_timestamp):
                    matchList = []
                    oldFound = True
                    print("Have reached games already inserted")
                    break

                queue = match['queue']
                if(queue == 0):
                    print('\tcustom game, skipping insertion')
                    continue
                matchId = match['gameId']

                #check to see if this match has already been seen from a previous summoners match list
                curr.execute("select 1 from match where gameId = ?", [matchId])
                if curr.fetchone() is not None: 
                    print("\tThis game has already been spoken for, skipping")
                    continue

                #Now we have the match specifics
                matchDto = matchByMatchId(matchId)

                if matchDto is None:
                    continue

                seasonId = matchDto['seasonId']
                gameVersion = matchDto['gameVersion']

                participantIdentities = matchDto['participantIdentities']
                participants = matchDto['participants']

                for participantIdDto in participantIdentities:
                    summonerName = participantIdDto['player']['summonerName']

                    curr.execute('select 1 from summoner where summonerName = ?', [summonerName])
                    if curr.fetchone() is None: continue

                    participantId = participantIdDto['participantId']

                    for participantDto in participants:
                        if participantDto['participantId'] != participantId: continue
                        #playerDto = participantDto['player']
                        
                        champion = participantDto['championId']
                        win = participantDto['stats']['win']
                        role = participantDto['timeline']['role']
                        lane = participantDto['timeline']['lane']
                        
                        inserted += 1
                        curr.execute('insert into match(gameId, summonerName, win, champion, role, lane, queue, seasonid, timestamp, gameVersion) values(?,?,?,?,?,?,?,?,?,?)', 
                                     (matchId, summonerName, win, champion, role, lane, queue, seasonId, timestamp, gameVersion))


            if oldFound is False:
                matchListDto = matchBySummoner(accountId, beginIndex)
                matchList = matchListDto["matches"]
            beginIndex += 100

    conn.commit()
    conn.close()   
    print(str(inserted) + " \"(Game, Summoner)\" pairs inserted")

if __name__=="__main__":
    main()
    