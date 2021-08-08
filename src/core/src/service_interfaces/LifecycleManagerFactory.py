# See the License for the specific language governing permissions and
# limitations under the License.
#
# Requires Python 2.7+

import json
import os
import shutil
import time
from core.src.bootstrap.Constants import Constants
from core.src.service_interfaces.LifecycleManager import LifecycleManager
from core.src.service_interfaces.LifecycleManagerAzure import LifecycleManagerAzure
from core.src.service_interfaces.LifecycleManagerARC import LifecycleManagerARC

class LifecycleManagerFactory(object):
    """ Parent class for LifecycleManagers of Azure and ARC ( auto assessment ), manages lifecycle within the extension wrapper ~ """
    def __init__(self, env_layer, execution_config, composite_logger, telemetry_writer):
        self.env_layer = env_layer
        self.execution_config = execution_config
        self.composite_logger = composite_logger
        self.telemetry_writer = telemetry_writer
        self.lifecycleManager_object = None

        #self.ext_state_file_path = os.path.join(self.execution_config.config_folder, Constants.EXT_STATE_FILE)
        #self.core_state_file_path = os.path.join(self.execution_config.config_folder, Constants.CORE_STATE_FILE)

    def getLifecycleManagerObject(self):
        if(self.lifecycleManager_object != None):
            return self.lifecycleManager_object

        current_vm_env = self.env_layer.get_vm_environment()
        if(current_vm_env == Constants.VM_ARC):
            self.lifecycleManager_object = LifecycleManagerARC(self.env_layer,self.execution_config,self.composite_logger, self.telemetry_writer)
        elif(current_vm_env == Constants.VM_AZURE):
            self.lifecycleManager_object = LifecycleManagerAzure(self.env_layer,self.execution_config,self.composite_logger, self.telemetry_writer)
        else:
            self.lifecycleManager_object = LifecycleManagerAzure(self.env_layer,self.execution_config,self.composite_logger, self.telemetry_writer)

        return self.lifecycleManager_object
