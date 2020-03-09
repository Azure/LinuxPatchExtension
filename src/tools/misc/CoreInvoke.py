from __future__ import print_function
import base64
import datetime
import sys
import json


def main(argv):
    exec_path = "MsftLinuxUpdateCore.py"

    sequence_number = 1
    environment_settings = {"logFolder": "scratch",
                            "configFolder": "scratch",
                            "statusFolder": "scratch"
                            }
    config_settings = {
        "operation": "Installation",
        "activityId": "f683ed4c-2c56-4aa0-bc67-f906ce35a0ff",
        "startTime": str(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")),
        "maximumDuration": "PT2H",
        "rebootSetting": "IfRequired",
        "classificationsToInclude": [],
        "patchesToInclude": ["*coreutils*"],
        "patchesToExclude": ["firefox*", "lib*"]
    }

    command = "sudo python " + exec_path + " -sequenceNumber {0} -environmentSettings \'{1}\' -configSettings \'{2}\'".format(sequence_number, base64.b64encode(json.dumps(environment_settings)), base64.b64encode(json.dumps(config_settings)))
    print("\nINVOCATION COMMAND:")
    print("\n" + command + "\n")


if __name__ == "__main__":
    main(sys.argv)