
# Azure Linux VM Patch Extension

Azure Linux VM Patch Extension allows users to securely update their Linux IaaS 
VMs with latest patches. It provides a two-fold solution of assessment and patching 
wherein, assessment identifies the patches available on the VM and patching enables 
users to select and install patches, while ensuring azure native availability 
and resiliency standards are met. 

# Reference Guide

## 1. Extension Configuration

Configurations expected in the request:

* `operation`: the operation expected to occur (Assessment/Installation/ConfigurePatching/NoOperation). 
NoOperation can be used to cancel an ongoing assess or patch operation. (**required for all 3 operations**) 
* `activityId`: GUID used to track the operation end to end (**required for all 3 operations**) 
* `startTime`: the expected start time of the operation in UTC (**required for all 3 operations**)
* `maximumDuration`: the expected maximum run time of the operation (**required for Installation**)
* `rebootSetting`: reboot preference during the operation (IfRequired/Never/Always) (**required for Installation**)
* `classificationsToInclude`: ["Critical", "Security"] as a unit (both have to be specified or neither) and/or ["Other"] 
(**optional for all operations**)
* `patchesToInclude`: packages to include during the operation. Package names and versions are supported (both with wildcards) 
(**optional for all operations**)
* `patchesToExclude`: packages to exclude during the operation. Package names and versions are supported (both with wildcards) 
(**optional for all operations**)
* `patchMode`: is the setting used to configure the automatic update by OS. Acceptable values: "ImageDefault" or "AutomaticByPlatform"
* `assessmentMode`: is the setting used to configure automatic assessment if desired. Acceptable values: "ImageDefault" or "AutomaticByPlatform"
* `maximumAssessmentInterval`: the expected maximum time interval expected between automatic assessments, if configured.

> Example:
>
> ```json
> {
>   "operation": "Assessment",
>   "activityId": "def820db-ec3c-4ecd-9d6c-cb95e6fd5231",
>   "startTime": "2021-08-10T23:37:14Z",
>   "maximumDuration": "PT2H",
>   "rebootSetting": "IfRequired",
>   "classificationsToInclude":["Critical","Security"],
>   "patchesToInclude": ["mysql-server", "snapd"],
>   "patchesToExclude": ["kernel*"],
>   "internalSettings": "test",
>   "maintenanceRunId": "2021-08-10T12:12:14Z",
>   "patchMode": "AutomaticByPlatform",
>   "assessmentMode": "AutomaticByPlatform",
>   "maximumAssessmentInterval": "PT3H"
> }
> ```

Of these, only `operation`, `activityId`, `startTime` are required for Assessment & NoOperation. Rest all apply to Installation.

## 2. Build and Test locally

* Run `python <Project-Path>\src\tools\Package-All.py`. This will generate LinuxPatchExtension.zip under `<Project-Path>\out\`
* Extract files from the zip to any location on your Linux machine. Note down this path.
* Add `HandlerEnvironment.json` following the reference `<Project-Path>\src\tools\references\HandlerEnvironment.json` within the folder containing extracted files. 
`HandlerEnvironment.json` defines the location where log, config and status files will be saved. Make sure to specify a directory/folder path for all 3 (can be any location within the machine)
* Create `<random-number>.settings` file with extension configuration for the request (Sample: `<Project-Path>\src\tools\references\12.settings`) 
and add this file into the configFolder path from HandlerEnvironment.json
* From within the extracted folder, run `.\MsftLinuxPatchExtShim.sh -e` to `enable` the extension. To get more details on all commands for the extension use --help.

## 3. Troubleshooting

Within your Azure VM, you can find logs/config files at these locations:

* Agent log: `/var/log/waagent.log`
* Extension logs: `under /var/log/azure/Microsoft.CPlat.Core.LinuxPatchExtension/`
* Other Extension files (such as status blob, config file, etc): `/var/lib/waagent/Microsoft.CPlat.Core.LinuxPatchExtension-<version>/`

Please open an issue on this GitHub repository if you encounter problems that
you could not debug with these log files.

## 4. Disclaimer

* **Data Collection**: The software may collect information about you and your use of the software and send it to Microsoft. 
Microsoft may use this information to provide services and improve our products and services. You may turn off the telemetry 
as described in the repository. There are also some features in the software that may enable you and Microsoft to collect data 
from users of your applications. If you use these features, you must comply with applicable law, including providing appropriate 
notices to users of your applications together with a copy of Microsoft's privacy statement. Our privacy statement is located 
at https://go.microsoft.com/fwlink/?LinkID=824704. You can learn more about data collection and use in the help documentation 
and our privacy statement. Your use of the software operates as your consent to these practices.

-----
This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/). 
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or 
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

