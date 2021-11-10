import requests
import config as cfg
import json
import csv
from BackupEntry_Class import BackupEntry as BE

def main():
    ticket = createBackupCheckTicket("tech")
    deviceList = createDeviceDictList("tech")

    deviceList = getDeviceSerials(deviceList)

    for device in deviceList:
        if(device.serial != "None"):
            device.alerts = getAlerts(device.serial)

    addTasks(deviceList, ticket)

def createBackupCheckTicket(team):
    """Creates a new ticket in Connectwise Manage on the current team's board. Returns the ticket number

    Args:
        team ([string]): The current team that the check is being done on

    Returns:
        [string]: The manage ticket #
    """

    # Json template for a new ticket to be generated
    # summary, [board][name], [contact][name][contactEmailAddress], [team][name], and [initial description]
    # need to be set
    ticketTemplate = json.load(open("./templates/newCheckTemplate.json"))


    ticketTemplate["summary"]             = "Test For backup tickets"
    ticketTemplate["board"]["name"]       = cfg.ticket[team]["board"]
    ticketTemplate["contact"]["name"]     = cfg.ticket[team]["name"]
    ticketTemplate["contactEmailAddress"] = cfg.ticket[team]["email"]
    ticketTemplate["team"]["name"]        = cfg.ticket[team]["team"]
    ticketTemplate["initialDescription"]  = "Testing the backup tickets"

    # API call returns as int, so must be cast as string to be added to endpoints
    return str(managePostAPICall(json.dumps(ticketTemplate), "service/tickets/"))


def createDeviceDictList(team):
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

    # Team name passed as arg, should match up with .csv of clients in /Clients/
    filename = "./Clients/" + team + ".csv"

    # Open the csv file
    with open(filename, 'r') as csvfile:
        csvreader = csv.reader(csvfile)

        # Skip the header row
        next(csvreader)

        # Cycle through each row of the csv file
        for row in csvreader:
            client = row[0]
            service = str(row[1])
            name = str(row[2])

            # create new object and add to list
            list.append(BE(client, service, name))

            

    return list

# Returns a dict of names:serial numbers
def getDeviceSerials(deviceList):
    """Takes the list of BackupEntry objects, performs an API call to get the list of devices from Datto
    and updates the objects with the correct serial numbers. Returns the updated list

    Args:
        deviceList [list.BE]: List of BackupEntry (BE) objects

    Returns:
        [list.BE]: List of BackupEntry (BE) objects
    """

    endpoint = "/bcdr/device?_page=1&_perPage=200&showHiddenDevices=0"
    # datto API call. Returns JSON results
    j = dattoAPICall(endpoint)

    # TODO: There has to be a more efficient way to do this
    # Iterate through all devices returned by API call
    for asset in j["items"]:
        # Iterate through all BackupEntries in current check. If name == current device, set serial number
        for device in deviceList:
            if(device.service == "datto"):
                if (device.backup == asset["name"]):
                    device.serial = asset["serialNumber"]

    return deviceList

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

    taskTemplate = json.load(open("./templates/newTaskTemplate.json"))
    taskTemplate["ticketID"] = ticket


    for device in deviceList:
        taskTemplate["notes"] = device.service + "\n" + device.client + "\n" + device.backup + "\n__________________________________________\n"
        alertText = ""

        # Add alerts to task
        if(device.alerts != "Not Checked"):
            for alert in device.alerts:
                # If there are backup alerts, cycle through them and add info to task
                alertText += "<b>Agent Name: " + alert["name"] + "</b>\n" 
                if(alert["backupErrors"] != None):

                    alertText += "BACKUP ERRORS: \n"
                    for x in alert["backupErrors"]:
                        alertText += "Timestamp: " + str(x["timestamp"]) + "\n"
                        alertText += "Status: " + str(x["status"]) + "\n"
                        alertText += "Error: " + str(x["error"]) + "\n"
                        alertText += "Screenshot: " + str(x["screenshot"]) + "\n"
                        alertText += "***********************************\n"

                if(alert["localErrors"] != None):
                    
                    alertText += "LOCAL ERRORS: \n"
                    for x in alert["backupErrors"]:
                        alertText += "Timestamp: " + str(x["timestamp"]) + "\n"
                        alertText += "Status: " + str(x["status"]) + "\n"
                        alertText += "Error: " + str(x["error"]) + "\n"
                        alertText += "Screenshot: " + str(x["screenshot"]) + "\n"
                        alertText += "***********************************"        
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

if __name__ == "__main__":
    main()