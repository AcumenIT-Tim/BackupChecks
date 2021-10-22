import requests
import config as cfg
import json

api = cfg.api["server"]
names = ["ASGSPBCS01", "BandM-Siris4", "CDJGSPBCS01", "DYCOSGSPBCS01", "GCGSPBCS01", "GCRAGSPBCS01", "JITGSPBCS01", "KSGSPBCS02", "LMGSPBCS", "MEIGSPBCS02",
"MEITXNAS1", "PINNGSPBCS01", "PREGGSPBCS02", "PROSRCBCS1", 'RESGSPBCS01', 'SCBARCAEBCS02', 'THRGSPBCS01', ]


def main():
    deviceList = createDeviceDictList()
    deviceList = getDeviceSerials(deviceList)

    for asset in deviceList:
        if(asset["serialNumber"] != "Not Found"):
            asset["alerts"] = getAlerts(asset["serialNumber"])



    for x in deviceList:
        print(x)
        
     
 


            

#                     # Alerts Is a list of dicts in followin format
#                     # 
#                     # [[{'name': 'test', 
#                     #    'errors': [{'timestamp': '1970-01-01T00:00:00+00:00', 
#                     #             'Status':'failure' 
#                     #             'error': None}]
#                     # }
#                     # ]]
#                     #                  

def createDeviceDictList():
    list = []
    for device in names:
        entry = {
            "name":device,
            "serialNumber": "Not Found",
            "alerts": "None"
        }
        list.append(entry)

    return list

# Returns a dict of names:serial numbers
def getDeviceSerials(deviceList):
    serialDict = {}
    endpoint = api + "/bcdr/device?_page=1&_perPage=200&showHiddenDevices=0"

    res = requests.get(endpoint, auth=(cfg.api["public"], cfg.api["private"]))
    status = statusCheck(res.status_code)

    if(status != True):
        print (status)
        return False

    j = res.json()

    # Creates a dict of device names and their serial numbers
    for asset in j["items"]:
        for device in deviceList:
            if (device["name"] == asset["name"]):
                device["serialNumber"] = asset["serialNumber"]

    return deviceList

def getAlerts(serial):
    endpoint = api + "/bcdr/device/"+ serial + "/asset"

    res = requests.get(endpoint, auth=(cfg.api["public"], cfg.api["private"]))

    assets = res.json()

    # Loop through all devices that are backed up
    failures = []

    for device in assets:
        # Ignore paused/archived
        if device["isPaused"] != True and device["isArchived"] != True:

            # Check available backups for issues
            alerts = checkBackups(device)

            if(alerts != "None"):
                x = {
                    "name":device["name"],
                    "errors": alerts
                }

                failures.append(x)

    if(len(failures) > 0):
        return failures
    else:
        return "None"
            
    

def checkBackups(device):   
    # Initiate empty list to hold error dicts
    errorList = []
    for backup in device["backups"]:
        if(backup["backup"]["status"] == "failure"):
            # Create a dict with error components to be added to error list


            if (backup["advancedVerification"]["screenshotVerification"] == None):
                screenshot = "None"
            else:
                screenshot = backup["advancedVerification"]["screenshotVerification"]["image"]


            error = {
                "timestamp": backup["timestamp"],
                "Status": backup["backup"]["status"],
                "error": backup["backup"]["errorMessage"],
                "screenshot": screenshot
            }

            errorList.append(error)



    if (len(errorList) == 0):
        return "None"
    else:
        return errorList

def statusCheck(statusCode):
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