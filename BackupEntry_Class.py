import config as cfg


class BackupEntry:
    def __init__(self, client, service, backup):
        self.client = client
        self.service = service
        self.backup = backup
        self.serial = "None"
        self.alerts = "Not Checked"
        self.taskID = "None"

    def print(self):
        print(self.client)
        print(self.service)
        print(self.backup)
        print(self.serial)
        print(self.alerts)
        print("_______________________________________")
   