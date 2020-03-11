import sys
from src.Constants import Constants


class InstallCommandHandler(object):

    def __init__(self, logger, ext_env_handler):
        self.logger = logger
        self.ext_env_handler = ext_env_handler

    def execute_handler_action(self):
        self.validate_os_type()
        self.validate_environment()
        self.logger.log("Install Command Completed")
        return Constants.ExitCode.Okay

    def validate_os_type(self):
        os_type = sys.platform
        self.logger.log("Validating OS. [Platform={0}]".format(os_type))
        if not os_type.__contains__('linux'):
            error_msg = "Incompatible system: This update is for Linux OS"
            self.logger.log_error_and_raise_new_exception(error_msg, Exception)
        return True

    def validate_environment(self):
        file = Constants.HANDLER_ENVIRONMENT_FILE
        env_settings_fields = Constants.EnvSettingsFields
        config_type = env_settings_fields.settings_parent_key
        self.logger.log("Validating file. [File={0}]".format(file))

        if self.ext_env_handler.handler_environment_json is not None and self.ext_env_handler.handler_environment_json is not Exception:
            if len(self.ext_env_handler.handler_environment_json) != 1:
                error_msg = "Incorrect file format. [File={0}]".format(file)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)

            self.validate_key(config_type, self.ext_env_handler.handler_environment_json[0], 'dict', True, file)
            self.validate_key(env_settings_fields.log_folder, self.ext_env_handler.handler_environment_json[0][config_type], ['str', 'unicode'], True, file)
            self.validate_key(env_settings_fields.config_folder, self.ext_env_handler.handler_environment_json[0][config_type], ['str', 'unicode'], True, file)
            self.validate_key(env_settings_fields.status_folder, self.ext_env_handler.handler_environment_json[0][config_type], ['str', 'unicode'], True, file)
            self.logger.log("Handler Environment validated")
        else:
            error_msg = "No content in file. [File={0}]".format(file)
            self.logger.log_error_and_raise_new_exception(error_msg, Exception)

    """ Validates json files for required key/value pairs """
    def validate_key(self, key, config_type, data_type, is_required, file):
        if is_required:
            # Required key doesn't exist in config file
            if key not in config_type:
                error_msg = "Config not found in file. [Config={0}] [File={1}]".format(key, file)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)
            # Required key doesn't have value
            elif data_type is not bool and not config_type[key]:
                error_msg = "Empty value error. [Config={0}]".format(key)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)
            # Required key does not have value of expected datatype
            elif type(config_type[key]).__name__  not in data_type:
                error_msg = "Unexpected data type. [config={0}] in [file={1}]".format(key, file)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)
        else:
            # Expected data type for an optional key
            if key in config_type and config_type[key] and type(config_type[key]).__name__  not in data_type:
                error_msg = "Unexpected data type. [config={0}] in [file={1}]".format(key, file)
                self.logger.log_error_and_raise_new_exception(error_msg, Exception)
