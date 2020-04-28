""" A patch assessment """
import time
from src.bootstrap.Constants import Constants


class PatchAssessor(object):
    """ Wrapper class of a single patch assessment """
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer, status_handler, package_manager):
        self.env_layer = env_layer
        self.execution_config = execution_config

        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.status_handler = status_handler

        self.package_manager = package_manager

    def start_assessment(self):
        """ Start an update assessment """
        self.composite_logger.log('\nStarting patch assessment...')
        self.status_handler.set_current_operation(Constants.ASSESSMENT)

        self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_TRANSITIONING)
        self.composite_logger.log("\nMachine Id: " + self.env_layer.platform.node())
        self.composite_logger.log("Activity Id: " + self.execution_config.activity_id)
        self.composite_logger.log("Operation request time: " + self.execution_config.start_time)

        self.composite_logger.log("\n\nGetting available patches...")
        self.package_manager.refresh_repo()
        self.status_handler.reset_assessment_data()

        for i in range(0, Constants.MAX_ASSESSMENT_RETRY_COUNT):
            try:
                packages, package_versions = self.package_manager.get_all_updates()
                self.telemetry_writer.send_debug_info("Full assessment: " + str(packages))
                self.status_handler.set_package_assessment_status(packages, package_versions)
                sec_packages, sec_package_versions = self.package_manager.get_security_updates()
                self.telemetry_writer.send_debug_info("Security assessment: " + str(sec_packages))
                self.status_handler.set_package_assessment_status(sec_packages, sec_package_versions, "Security")
                self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_SUCCESS)
                break
            except Exception as error:
                if i < Constants.MAX_ASSESSMENT_RETRY_COUNT:
                    error_msg = 'Retryable error retrieving available patches: ' + repr(error)
                    self.composite_logger.log_warning(error_msg)
                    self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                    time.sleep(2*(i + 1))
                else:
                    error_msg = 'Error retrieving available patches: ' + repr(error)
                    self.composite_logger.log_error(error_msg)
                    self.status_handler.add_error_to_status(error_msg, Constants.PatchOperationErrorCodes.DEFAULT_ERROR)
                    if Constants.ERROR_ADDED_TO_STATUS not in repr(error):
                        error.args = (error.args, "[{0}]".format(Constants.ERROR_ADDED_TO_STATUS))
                    self.status_handler.set_assessment_substatus_json(status=Constants.STATUS_ERROR)
                    raise

        self.composite_logger.log("\nPatch assessment competed.\n")
        return True
