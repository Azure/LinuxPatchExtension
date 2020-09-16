import time
import datetime

sleep_time = 0.01  # in seconds


def read_file():
    try:
        file_loc = r'/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.7/status/21.status'
        file_handle = open(file_loc, 'r')
        data = file_handle.read()
        print(data)
        file_handle.close()
    except Exception as error:
        print("Error occurred during file operation: " + repr(error))
        data = "Error occurred during file operation: " + repr(error)

    try:
        write_output_to_file = '/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-1.6.7/status/21.status.log'
        write_file_handle = open(write_output_to_file, 'a')
        write_file_handle.write("TimeStamp: " + str(datetime.datetime.utcnow()) + "\t" + str(data) + "\n\n\n\n\n")
        write_file_handle.close()
    except Exception as error:
        print("Error occurred during file operation: " + repr(error))


while True:  # This loop runs forever
    read_file()
    time.sleep(sleep_time)

