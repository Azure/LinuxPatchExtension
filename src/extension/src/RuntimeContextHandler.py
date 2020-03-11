import datetime
import time
from src.Constants import Constants


class RuntimeContextHandler(object):
    def __init__(self, logger):
        self.logger = logger
        self.core_state_fields = Constants.CoreStateFields

    def terminate_processes_from_previous_operation(self, process_handler, core_state_content):
        """ Terminates all running processes from the previous request """
        self.logger.log("Verifying if previous patch operation is still in progress")
        if core_state_content is None or core_state_content.__getattribute__(self.core_state_fields.completed).lower() == 'true':
            self.logger.log("Previous request is complete")
            return
        # verify if processes from prev request are running
        running_process_ids = process_handler.identify_running_processes(core_state_content.__getattribute__(self.core_state_fields.process_ids))
        if len(running_process_ids) != 0:
            for pid in running_process_ids:
                process_handler.kill_process(pid)

    def process_previous_patch_operation(self, core_state_handler, process_handler, prev_patch_max_end_time, core_state_content):
        """ Waits for the previous request action to complete for a specific time, terminates previous process if it goes over that time """
        self.logger.log("Verifying if previous patch operation is still in progress")
        core_state_content = core_state_handler.read_file() if core_state_content is None else core_state_content
        if core_state_content is None or core_state_content.__getattribute__(self.core_state_fields.completed).lower() == 'true':
            self.logger.log("Previous request is complete")
            return
        # verify if processes from prev request are running
        running_process_ids = process_handler.identify_running_processes(core_state_content.__getattribute__(self.core_state_fields.process_ids))
        if len(running_process_ids) != 0:
            is_patch_complete = self.check_if_patch_completes_in_time(prev_patch_max_end_time, core_state_content.__getattribute__(self.core_state_fields.last_heartbeat), core_state_handler)
            if is_patch_complete:
                self.logger.log("Previous request is complete")
                return
            for pid in running_process_ids:
                self.logger.log("Previous request did not complete in time. Terminating all of it's running processes.")
                process_handler.kill_process(pid)

    def check_if_patch_completes_in_time(self, time_for_prev_patch_to_complete, core_state_last_heartbeat, core_state_handler):
        """ Waits for the previous request to complete in given time, with intermittent status checks """
        if type(time_for_prev_patch_to_complete) is not datetime.datetime:
            raise Exception("System Error: Unable to identify the time to wait for previous request to complete")
        max_wait_interval_in_seconds = 60
        current_time = datetime.datetime.utcnow()
        remaining_wait_time = (time_for_prev_patch_to_complete - current_time).total_seconds()
        core_state_content = None
        while remaining_wait_time > 0:
            next_wait_time_in_seconds = max_wait_interval_in_seconds if remaining_wait_time > max_wait_interval_in_seconds else remaining_wait_time
            core_state_last_heartbeat = core_state_last_heartbeat if core_state_content is None else core_state_content.__getattribute__(self.core_state_fields.last_heartbeat)
            self.logger.log("Previous patch operation is still in progress with last status update at {0}. Waiting for a maximum of {1} seconds for it to complete with intermittent status change checks. Next check will be performed after {2} seconds.".format(str(core_state_last_heartbeat), str(remaining_wait_time), str(next_wait_time_in_seconds)))
            time.sleep(next_wait_time_in_seconds)
            remaining_wait_time = (time_for_prev_patch_to_complete - datetime.datetime.utcnow()).total_seconds()
            # read CoreState.json file again, to verify if the previous processes is completed
            core_state_content = core_state_handler.read_file()
            if core_state_content.__getattribute__(self.core_state_fields.completed).lower() == 'true':
                return True
        return False
