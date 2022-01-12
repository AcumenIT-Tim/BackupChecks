import requests
import config as cfg
import json
import csv
import mysql.connector
from BackupEntry_Class import BackupEntry as BE
from pathlib import Path

def main():
    db = mysql.connector.connect(
        host     = cfg.mySQL_creds["host"],
        port     = cfg.mySQL_creds["port"],
        user     = cfg.mySQL_creds["user"],
        password = cfg.mySQL_creds["password"],
        database = cfg.mySQL_creds["database"]
    )


    for team in range(3):
        print("Creating ticket for Team " + str(team))
        ticket     = createBackupCheckTicket(db, 3)
        print(str(ticket))
        print("Building device List for Team " + str(team))
        deviceList = createDeviceDictList(db,team)

        print("Getting alerts for Team " + str(team))
        for device in deviceList:
            if(device.service == "Datto"):
                device.alerts = getAlerts(device.serial)

        print("Adding tasks for Team " + str(team))
        addTasks(deviceList, ticket)
        print("Completed Team " + str(team))

def createBackupCheckTicket(dbConn,team):
    """Creates a new ticket in Connectwise Manage on the current team's board. Returns the ticket number

    Args:
        team ([string]): The current team that the check is being done on

    Returns:
        [string]: The manage ticket #

    """

    cursor =dbConn.cursor()
    sql = "SELECT * FROM teams WHERE teamID="+str(team)

    try:
        cursor.execute(sql)
    except (mysql.connector.Error, mysql.connector.Warning) as e:
        # TODO Call error handling and do something
        print(e)
        return 0
    
    # Query results in order: teamID, teamName,teamLead,teamLeadEmail,board
    contact = cursor.fetchone()

    # Json template for a new ticket to be generated
    # summary, [board][name], [contact][name][contactEmailAddress], [team][name], and [initial description]
    # need to be set
    path = Path(__file__).parent / "./templates/newCheckTemplate.json"
    with path.open() as f:
        ticketTemplate = json.load(f)


    ticketTemplate["summary"]             = "(TESTING)" + contact[1] + " Automated backup checks"
    ticketTemplate["board"]["name"]       = contact[4]
    ticketTemplate["contact"]["name"]     = contact[2]
    ticketTemplate["contactEmailAddress"] = contact[3]
    ticketTemplate["team"]["name"]        = contact[1]
    ticketTemplate["initialDescription"]  = """I am testing semi-automated backup checks. This 1st version should automatically
    check backups in Datto and, if any errors are detected, add a summary in tasks. While it is in Beta, please continue backup checks
    as normal and cross reference with this ticket. If you find any differences please let me know. - Tim"""

    # API call returns as int, so must be cast as string to be added to endpoints


    return str(managePostAPICall(json.dumps(ticketTemplate), "service/tickets/"))


def createDeviceDictList(dbConn, team):
    """Reads a CSV file with the corresponding team name that contains client name
    backup provider, and appliance name. Creates a BackupEntry object (found in BackupEntry_Class.py)
    and appends it to a list

    Args:
        team (string): string of the team name (alpha, bravo, charlie, tech)

    Returns:
        list: list of BackupEntry Objects
    """
    # Initiate list object to hold the devices
    list = []

    cursor =dbConn.cursor()
    sql = "SELECT * FROM backups WHERE teamID=" + str(team)

    try:
        cursor.execute(sql)
    except (mysql.connector.Error, mysql.connector.Warning) as e:
        # TODO Call error handling and do something
        print(e)
        return 0

    res = cursor.fetchall()

    # Open the csv file
    for x in res:
        client = x[1]
        service = x[2]
        name = x[3]
        serial = x[4]
        notes = x[6]

        # create new object and add to list
        list.append(BE(client, service, name, serial,notes))


    return list

def getAlerts(serial):
    """Takes the serial number of a device, performs an API call to get info of all available agents, and returns a list of dicts 
    for each. The dict contains 2 lists, "backupErrors" and "localErrors".

    Args:
        serial ([string]): serial number of the backup device

    Returns:
        list.dict: List of dicts with keys "backupErrors" and "localErrors". Values are lists of errors
    """
    endpoint = "/bcdr/device/"+ serial + "/asset"

    assets = dattoAPICall(endpoint)

    # Loop through all devices that are backed up
    failures = []

    for device in assets:
        # Ignore paused/archived
        if device["isPaused"] != True and device["isArchived"] != True:

            # Check available backups for issues
            alerts = checkBackups(device)


            if(len(alerts["backup"]) > 0):
                backupErrors = alerts["backup"]
            else:
                backupErrors = "No Errors"

            if(len(alerts["local"]) == len(assets)):
                localErrors = "NA"
            elif(len(alerts["local"]) > 0):
                localErrors = alerts["local"]
            else:
                localErrors = "No Errors"


            x = {
                "name":device["name"],
                "backupErrors": backupErrors,
                "localErrors": localErrors
            }

            if(backupErrors != "No Errors" and localErrors != "No Errors"):
                failures.append(x)

    return failures
            
def checkBackups(device):   
    # TODO: Add Time of latest error and check against current time to not report on resolved issues

    # Initiate empty lists to hold error dicts
    errorList       = {
        "backup": "None",
        "local": "None"
    }
    backupErrorList = []
    localErrorList  = []

    for backup in device["backups"]:
        if(backup["backup"]["status"] == "failure"):
            # Create a dict with error components to be added to error list


            if (backup["advancedVerification"]["screenshotVerification"] == None):
                screenshot = "None"
            else:
                screenshot = backup["advancedVerification"]["screenshotVerification"]["image"]


            error = {
                "timestamp": backup["timestamp"],
                "status": backup["backup"]["status"],
                "error": backup["backup"]["errorMessage"],
                "screenshot": screenshot
            }

            backupErrorList.append(error)

        # If the backup was successfull, check local verification
        else:
            if(backup["localVerification"]["status"] == "failure"):
                if (backup["advancedVerification"]["screenshotVerification"] == None):
                    screenshot = "None"
                else:
                    screenshot = backup["advancedVerification"]["screenshotVerification"]["image"]

                error = {
                "timestamp": backup["timestamp"],
                "status": backup["localVerification"]["status"],
                "error": backup["localVerification"]["errors"],
                "screenshot": screenshot
                }

                localErrorList.append(error)

    errorList["backup"] = backupErrorList
    errorList["local"]  = localErrorList
    return errorList

def dattoAPICall(endpoint):
    try:
        r = requests.get(cfg.datto_api["server"] + endpoint, auth=(cfg.datto_api["public"], cfg.datto_api["private"]))
        r.raise_for_status()
    except:
        print(r.text)
        raise

    return r.json()

def manageGetAPICall(endpoint):
    try:
        r = requests.get(cfg.manage_api["server"] + endpoint, headers=cfg.manage_api["header"])
        # request has been made
        r.raise_for_status()
    except:
        print(r.text)
        raise

    return r.json()

def managePostAPICall(payload, endpoint):
    """Takes a json payload and api endpoint and performs a POST action to the manage server. Returns POST Id

    Args:
        payload (json): Json to be posted to manage
        endpoint (string): API endpoint added to URL

    Returns:
        int: returns the ID of the post. (ticket # for new ticket, task # for new task)
    """
    try:
        r = requests.post(cfg.manage_api["server"] + endpoint, headers=cfg.manage_api["header"], data=payload)
        # request has been made
        r.raise_for_status()
    except:
        print(type(payload))
        print(r.text)
        raise
    j = r.json()
    return j["id"]

def addTasks(deviceList, ticket):

    """Takes a json payload and api endpoint and performs a POST action to the manage server. Returns POST Id

    Args:
        payload (json): Json to be posted to manage
        endpoint (string): API endpoint added to URL

    Returns:
        int: returns the ID of the post. (ticket # for new ticket, task # for new task)
    """
    endpoint = "service/tickets/" + ticket + "/tasks"

    path = Path(__file__).parent / "./templates/newTaskTemplate.json"
    with path.open() as f:
        taskTemplate = json.load(f)


    taskTemplate["ticketID"] = ticket


    for device in deviceList:
        taskTemplate["notes"] = "Name: " + device.client + "\n"
        taskTemplate["notes"] += "Service: " + device.service + "\n"
        taskTemplate["notes"] += "Backup Device: " +  device.backup + "\n"
        taskTemplate["notes"] += "Notes:  "+ str(device.notes)+"\n__________________________________________\n"
        alertText = ""

        # Add alerts to task
        if(device.alerts != "Not Checked"):
            if(len(device.alerts) > 0):
                for alert in device.alerts:
                    # If there are backup alerts, cycle through them and add info to task
                    alertText += "Agent Name: " + alert["name"] + "\n" 
                    print(len(alert["backupErrors"]))
                    if(len(alert["backupErrors"]) > 0):

                        alertText += "BACKUP ERRORS: \n"
                        for x in alert["backupErrors"]:
                            alertText += "Timestamp: " + str(x["timestamp"]) + "\n"
                            alertText += "Status: " + str(x["status"]) + "\n"
                            alertText += "Error: " + str(x["error"]) + "\n"
                            alertText += "Screenshot: " + str(x["screenshot"]) + "\n"
                            alertText += "***********************************\n"
                    else:
                        alertText  += "No backup errors found\n"
                    if(alert["localErrors"] != None):
                        
                        alertText += "LOCAL ERRORS: \n"
                        for x in alert["backupErrors"]:
                            alertText += "Timestamp: " + str(x["timestamp"]) + "\n"
                            alertText += "Status: " + str(x["status"]) + "\n"
                            alertText += "Error: " + str(x["error"]) + "\n"
                            alertText += "Screenshot: " + str(x["screenshot"]) + "\n"
                            alertText += "***********************************\n"      
                    else:
                        alertText  += "No backup errors found\n"  
                    taskTemplate["notes"] += str(alertText) + "\n"
            else:
                alertText = "No backup errors found\n"
                taskTemplate["notes"] += str(alertText) + "\n"

        else:
            taskTemplate["notes"] += str(device.alerts) + "\n"

        
        managePostAPICall(json.dumps(taskTemplate), endpoint)

    return 

def statusCheck(statusCode):
    # TODO Implement status check at all API calls. 
    #  Flesh out error handling
    if (statusCode == 200):
        return True
    elif (statusCode == 403):
        return "403 - Invalid authentication"
    elif (statusCode == 500):
        return "500 - An error occured"
    else:
        return "unknown error - " + str(statusCode)

def errorHandling():
    # TODO Add error handling.
    # Error logging, tech email,etc
    pass

if __name__ == "__main__":
    main()