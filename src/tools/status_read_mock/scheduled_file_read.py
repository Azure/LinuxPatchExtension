import time
import datetime

sleep_time = 0.01  # in seconds


def read_file_and_log_content():
    try:
        # add path of the file to be read
        # eg: file_path = '/test/1.txt'
        file_path = ''
        with open(file_path, 'r') as file_handle:
            data = file_handle.read()
            print(data)
    except Exception as error:
        print("Error occurred during file operation: " + repr(error))
        data = "Error occurred during file operation: " + repr(error)

    try:
        # add the location of the log file that will contain the contents of the file that is read. The log file will be created if it does not exist.
        # NOTE: make sure the file name is diff from the one which is read
        # eg: write_output_to_file = '/test/1.txt.log'
        write_output_to_file = ''
        write_file_handle = open(write_output_to_file, 'a')
        write_file_handle.write("TimeStamp: " + str(datetime.datetime.utcnow()) + "\t" + str(data) + "\n\n\n\n\n")
        write_file_handle.close()
    except Exception as error:
        print("Error occurred during file operation: " + repr(error))


while True:  # This loop runs forever
    read_file_and_log_content()
    time.sleep(sleep_time)

