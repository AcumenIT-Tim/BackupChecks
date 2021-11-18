import config as cfg


class BackupEntry:
    def __init__(self, client, service, backup, serial = "None", notes="None"):
        self.client = client
        self.service = service
        self.backup = backup
        self.serial = serial
        self.notes  = notes
        self.alerts = "Not Checked"
        self.taskID = "None"

    def print(self):
        print("Client: ",self.client)
        print("Service: ",self.service)
        print("DeviceName: ",self.backup)
        print("Serial: ",self.serial)
        print("Notes: ",self.notes)
        print("Alerts: ",self.alerts)
        print("_______________________________________")
   